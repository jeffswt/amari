from typing import Any, Dict, Generic, List

from typing_extensions import ParamSpec, Protocol

Args = ParamSpec("Args")


class CallableNode(Generic[Args], Protocol):
    def __call__(self, *args: Args.args, **kwargs: Args.kwargs) -> None:
        """Invoke delegated function. Behavior of this call is dependent on the
        current environment."""

        raise NotImplementedError()

    def _build(self, *args: Args.args, **kwargs: Args.kwargs) -> None:
        """Build mode constructs AML components without actually executing them.
        This step records the component configurations and call arguments for
        later scheduling in the pipelines."""

        raise NotImplementedError()

    def _run_py(self, *args: Args.args, **kwargs: Args.kwargs) -> None:
        """Invoke delegated function. This is equivalent to __call__ under
        debug mode (instead of building components) or CLI mode, when the
        function is neither in a pipeline nor in a CLI context."""

        raise NotImplementedError()

    def _run_yaml(self, kwargs: Dict[str, Any]) -> None:
        """Call function with AML-ish arguments. This happens only when the
        function is in a pipeline context."""

        raise NotImplementedError()

    def _run_cli(self, argv: List[str]) -> None:
        """Delegating function to main CLI entrypoint. This can be called in
        the global scope of the script if had it been a main module."""

        raise NotImplementedError()

    pass
