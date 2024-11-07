import dataclasses
import unittest
from typing import Any, Callable, Dict, List, Optional

from ..typecheck.args import parse_function
from ..utils.pyctx import PyCtx
from ..utils.types import guard_never
from .env import ComponentBuildEnv
from .fnexec import (
    fn_kwargs_from_cli,
    fn_kwargs_from_py,
    fn_kwargs_from_yaml,
    fn_kwargs_into_yaml,
)
from .nodes import Args, CallableNode


class _FunctionalComponent(CallableNode[Args]):
    def __init__(
        self,
        fn: Callable[Args, None],
        name: str,
        display_name: str,
        version: str,
        description: Optional[str],
        is_deterministic: bool,
        tags: Optional[Dict[str, str]],
    ) -> None:
        self.fn = fn
        self.name = name
        self.display_name = display_name
        self.version = version
        self.description = description
        self.is_deterministic = is_deterministic
        self.tags = tags

        self.parsed_fn = parse_function(fn)

    def __call__(self, *args: Args.args, **kwargs: Args.kwargs) -> None:
        env = ComponentBuildEnv.get()
        if env == ComponentBuildEnv.build:
            return self._build(*args, **kwargs)
        elif env == ComponentBuildEnv.run:
            return self._run_py(*args, **kwargs)
        else:
            guard_never(env)

    def _build(self, *args: Args.args, **kwargs: Args.kwargs) -> None:
        values = fn_kwargs_from_py(
            name=self.name, parsed_fn=self.parsed_fn, args=args, kwargs=kwargs
        )
        raw_values = fn_kwargs_into_yaml(parsed_fn=self.parsed_fn, kwargs=values)
        BuiltComponentSink.put(
            BuiltComponentConfig(component=self, raw_kwargs=raw_values)
        )
        return

    def _run_py(self, *args: Args.args, **kwargs: Args.kwargs) -> None:
        values = fn_kwargs_from_py(
            name=self.name, parsed_fn=self.parsed_fn, args=args, kwargs=kwargs
        )
        return self.fn(**values)  # type: ignore

    def _run_yaml(self, kwargs: Dict[str, Any]) -> None:
        values = fn_kwargs_from_yaml(parsed_fn=self.parsed_fn, kwargs=kwargs)
        return self.fn(**values)  # type: ignore

    def _run_cli(self, argv: List[str]) -> None:
        values = fn_kwargs_from_cli(self.parsed_fn, argv)
        return self.fn(**values)  # type: ignore

    pass


@dataclasses.dataclass
class BuiltComponentConfig:
    # since the kwargs would be remembered & scheduled by a pipeline, here
    # we record everything in yaml and no positional args are kept
    component: _FunctionalComponent
    # this must be in yaml format to be usable by shrike
    raw_kwargs: Dict[str, Any]
    pass


class BuiltComponentSink:
    """Stores compiled component configs here for later use."""

    _ComponentSinkCtx: PyCtx["BuiltComponentSink"] = PyCtx(
        key="amari.comps.BuiltComponentSink"
    )

    def __init__(self):
        self._sink: List[BuiltComponentConfig] = []

    @staticmethod
    def create() -> "BuiltComponentSink":
        self = BuiltComponentSink()
        BuiltComponentSink._ComponentSinkCtx.append(self, offset=1)
        return self

    @staticmethod
    def put(config: BuiltComponentConfig) -> None:
        self = BuiltComponentSink._ComponentSinkCtx.get()
        if not self:
            raise ValueError("cannot put BuiltComponentConfig here: not in build mode")
        self[-1]._sink.append(config)
        return

    def dump(self) -> List[BuiltComponentConfig]:
        return list(self._sink)

    pass


def component(
    name: str,
    display_name: str,
    version: str = "0.0.1",
    description: Optional[str] = None,
    is_deterministic: bool = True,
    tags: Optional[Dict[str, str]] = None,
):
    def _decorate(fn: Callable[Args, None]) -> _FunctionalComponent[Args]:
        return _FunctionalComponent[Args](
            fn=fn,
            name=name,
            display_name=display_name,
            version=version,
            description=description,
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
            description="""This is a test component.""",
        )
        def foo(x_num: int, y_s: List[str] = ["default"]) -> None:
            output.append(f"{x_num} {y_s}")

        foo._run_py(1, y_s=["2"])
        foo._run_py(3)
        foo.parsed_fn.fields[1].py_default = ["DEFAULT", "MORE"]  # hack it
        foo._run_cli(["--x_num", "4"])
        self.assertEqual(output, ["1 ['2']", "3 ['default']", "4 ['DEFAULT', 'MORE']"])

    def test_component_sink(self):
        sink = BuiltComponentSink.create()

        @component(
            name="amari.comps.test.bar",
            display_name="Bar",
            version="0.0.1",
            description="""This is another test component.""",
        )
        def bar(x_num: int, y_s: List[str] = ["default"]) -> None:
            _ = x_num, y_s

        bar._build(1, y_s=["2"])
        bar._build(3)
        bar.parsed_fn.fields[1].py_default = ["DEFAULT"]  # hack it
        bar._build(4)
        built = sink.dump()
        self.assertEqual(len(built), 3)
        self.assertEqual(built[0].raw_kwargs, {"x_num": 1, "y_s": '["2"]'})
        self.assertEqual(built[1].raw_kwargs, {"x_num": 3, "y_s": '["default"]'})
        self.assertEqual(built[2].raw_kwargs, {"x_num": 4, "y_s": '["DEFAULT"]'})

    pass
