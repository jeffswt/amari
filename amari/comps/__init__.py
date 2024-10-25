from typing import Callable, Generic, Optional

from typing_extensions import ParamSpec

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
        tag_contact: Optional[str],
    ) -> None:
        """Private constructor for wrapping up wrappers."""

        self.fn = fn
        self.name = name
        self.display_name = display_name
        self.version = version
        self.docs = docs
        self.is_deterministic = is_deterministic
        self.tag_contact = tag_contact

    def __call__(self, *args: Args.args, **kwargs: Args.kwargs) -> None:
        """Invoke delegated function."""

        return self.fn(*args, **kwargs)

    pass


def component(
    name: str,
    display_name: str,
    version: str = "0.0.1",
    docs: Optional[str] = None,
    is_deterministic: bool = True,
    tag_contact: Optional[str] = None,
):
    def _decorate(fn: Callable[Args, None]) -> _FunctionalComponent[Args]:
        return _FunctionalComponent[Args](
            fn=fn,
            name=name,
            display_name=display_name,
            version=version,
            docs=docs,
            is_deterministic=is_deterministic,
            tag_contact=tag_contact,
        )

    return _decorate


@component(
    name="amari.comps.foo",
    display_name="Foo",
    version="0.0.1",
    docs="""This is a test component.""",
)
def foo(x: int, y: str = "") -> None:
    return


x = foo(1, "2")
help(foo)
