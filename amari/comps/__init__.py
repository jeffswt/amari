import copy
import dataclasses
import sys
import unittest
from typing import Any, Callable, Dict, Generic, List, Optional

from typing_extensions import ParamSpec

from ..typecheck.args import parse_function
from ..utils.pyctx import PyCtx

Args = ParamSpec("Args")


class _FunctionalComponent(Generic[Args]):
    # TODO: make this abstract class so that pipelines could also share the
    #       same call/cli/build polymorphism.
    def __init__(
        self,
        fn: Callable[Args, None],
        name: str,
        display_name: str,
        version: str,
        docs: Optional[str],
        is_deterministic: bool,
        tags: Optional[Dict[str, str]],
    ) -> None:
        """Private constructor for wrapping up wrappers."""

        self.fn = fn
        self.name = name
        self.display_name = display_name
        self.version = version
        self.docs = docs
        self.is_deterministic = is_deterministic
        self.tags = tags

        self.parsed_fn = parse_function(fn)

    def __call__(self, *args: Args.args, **kwargs: Args.kwargs) -> None:
        """Invoke delegated function."""

        return self.fn(*args, **kwargs)

    def run_py(self, *args: Args.args, **kwargs: Args.kwargs) -> None:
        """Invoke delegated function. This is equivalent to __call__ under
        debug mode (instead of building components) or CLI mode."""

        values = self.__convert_to_kwargs(*args, **kwargs)
        return self.fn(**values)  # type: ignore

    def __convert_to_kwargs(
        self, *args: Args.args, **kwargs: Args.kwargs
    ) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        for i, field in enumerate(self.parsed_fn.fields):
            if i < len(args):
                value = args[i]
            elif field.name in kwargs:
                value = kwargs[field.name]
            else:
                if field.py_default is ...:
                    raise TypeError(
                        f"{self.display_name}() missing required positional argument: '{field.name}'"
                    )
                value = copy.deepcopy(field.py_default)
            validation_err = field.draft.fn_post_validate(value)
            if validation_err:
                raise ValueError(f"invalid value for '{field.name}': {validation_err}")
            values[field.name] = value
        return values

    def run_build(self, *args: Args.args, **kwargs: Args.kwargs) -> None:
        """Build mode constructs AML components without actually executing them.
        This step records the component configurations and call arguments for
        later scheduling in the pipelines."""

        values = self.__convert_to_kwargs(*args, **kwargs)
        _ComponentSink.put(_ComponentConfig(component=self, kwargs=values))
        return

    def run_cli(self, argv: Optional[List[str]] = None) -> None:
        """Delegating function to main CLI entrypoint. This is typically called
        in the global scope of the script if had it been a main module. Example:

        ```python
        if __name__ == "__main__":
            foo.run_cli()
        ```"""

        if argv is None:
            argv = sys.argv[1:]

        fields = {field.name: field for field in self.parsed_fn.fields}
        kwargs: Dict[str, Any] = {}
        for i in range(0, len(argv), 2):
            # obtain
            raw_key = argv[i]
            if not raw_key.startswith("--"):
                raise KeyError(f"invalid option '{raw_key}'")
            if i + 1 >= len(argv):
                raise ValueError(f"missing value for '{raw_key}'")
            raw_value = argv[i + 1]
            # evaluate
            key = raw_key[2:]
            if key not in fields:
                raise KeyError(f"unknown option '{raw_key}'")
            field = fields[key]
            value = field.draft.fn_load_cli(raw_value)
            validation_err = field.draft.fn_post_validate(value)
            if validation_err:
                raise ValueError(f"invalid value for '{raw_key}': {validation_err}")
            kwargs[key] = value
        return self.fn(**kwargs)  # type: ignore

    pass


@dataclasses.dataclass
class _ComponentConfig:
    # since the kwargs would be remembered & scheduled by a pipeline, here
    # we record everything in yaml and no positional args are kept
    component: _FunctionalComponent
    kwargs: Dict[str, Any]
    pass


class _ComponentSink:
    """Stores compiled component configs here for later use."""

    _ComponentSinkCtx: PyCtx["_ComponentSink"] = PyCtx(key="amari.comps._ComponentSink")

    def __init__(self):
        self._sink: List[_ComponentConfig] = []

    @staticmethod
    def create() -> "_ComponentSink":
        self = _ComponentSink()
        _ComponentSink._ComponentSinkCtx.append(self, offset=1)
        return self

    @staticmethod
    def put(config: _ComponentConfig) -> None:
        self = _ComponentSink._ComponentSinkCtx.get()
        if not self:
            raise ValueError("cannot put _ComponentConfig here: not in build mode")
        self[-1]._sink.append(config)
        return

    def dump(self) -> List[_ComponentConfig]:
        return list(self._sink)

    pass


def component(
    name: str,
    display_name: str,
    version: str = "0.0.1",
    docs: Optional[str] = None,
    is_deterministic: bool = True,
    tags: Optional[Dict[str, str]] = None,
):
    def _decorate(fn: Callable[Args, None]) -> _FunctionalComponent[Args]:
        return _FunctionalComponent[Args](
            fn=fn,
            name=name,
            display_name=display_name,
            version=version,
            docs=docs,
            is_deterministic=is_deterministic,
            tags=tags,
        )

    return _decorate


class ComponentTest(unittest.TestCase):
    def test_component_run(self):
        output: List[str] = []

        @component(
            name="amari.comps.test.foo",
            display_name="Foo",
            version="0.0.1",
            docs="""This is a test component.""",
        )
        def foo(x_num: int, y_s: str = "default") -> None:
            output.append(f"{x_num} {y_s}")

        foo.run_py(1, y_s="2")
        foo.run_cli(["--x_num", "3"])
        self.assertEqual(output, ["1 2", "3 default"])

    def test_component_sink(self):
        sink = _ComponentSink.create()

        @component(
            name="amari.comps.test.bar",
            display_name="Bar",
            version="0.0.1",
            docs="""This is another test component.""",
        )
        def bar(x_num: int, y_s: str = "default") -> None:
            _ = x_num, y_s

        bar.run_build(1, y_s="2")
        bar.run_build(3)
        built = sink.dump()
        self.assertEqual(len(built), 2)
        self.assertEqual(built[0].kwargs, {"x_num": 1, "y_s": "2"})
        self.assertEqual(built[1].kwargs, {"x_num": 3, "y_s": "default"})

    pass
