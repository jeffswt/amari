import copy
import sys
import unittest
from typing import Any, Callable, Dict, Generic, List, Optional

from typing_extensions import ParamSpec

from ..typecheck.args import parse_function

Args = ParamSpec("Args")


class _FunctionalComponent(Generic[Args]):
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
        debug mode (instead of building components)."""

        values: Dict[str, Any] = {}
        for i, field in enumerate(self.parsed_fn.fields):
            if i < len(args):
                value = args[i]
            elif field.name in kwargs:
                value = kwargs[field.name]
                values[field.name] = value
            else:
                if field.py_default is ...:
                    raise TypeError(
                        f"{self.display_name}() missing required positional argument: '{field.name}'"
                    )
                value = copy.deepcopy(field.py_default)
                values[field.name] = value
            validation_err = field.draft.fn_post_validate(value)
            if validation_err:
                raise ValueError(f"invalid value for '{field.name}': {validation_err}")
        return self.fn(*args, **values)

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
    def test_component(self):
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

    pass
