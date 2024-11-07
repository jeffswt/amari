import unittest
from typing import Any, Callable, Dict, List, Optional

from ..comps.env import BuiltComponentConfig, BuiltComponentSink, ComponentBuildEnv
from ..comps.fnexec import (
    fn_kwargs_from_cli,
    fn_kwargs_from_py,
    fn_kwargs_from_yaml,
    fn_kwargs_into_yaml,
)
from ..comps.nodes import Args, CallableNode
from ..typecheck.args import parse_function
from ..utils.types import guard_never


class _FunctionalPipeline(CallableNode[Args]):
    def __init__(
        self,
        fn: Callable[Args, None],
        name: str,
        display_name: str,
        version: str,
        description: Optional[str],
    ) -> None:
        self.fn = fn
        self.name = name
        self.display_name = display_name
        self.version = version
        self.description = description

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
        # capture pipeline component children
        ComponentBuildEnv.set(ComponentBuildEnv.build)

        def _capture():
            sink = BuiltComponentSink.create()
            self.fn(**values)  # type: ignore
            return sink.dump()

        children = _capture()
        # collect info for the pipeline
        raw_values = fn_kwargs_into_yaml(parsed_fn=self.parsed_fn, kwargs=values)
        BuiltComponentSink.put(
            BuiltComponentConfig(
                component=self, raw_kwargs=raw_values, children=children
            )
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


def pipeline(
    name: str,
    display_name: Optional[str] = None,
    version: str = "0.0.1",
    description: Optional[str] = None,
):
    def _decorate(fn: Callable[Args, None]) -> _FunctionalPipeline[Args]:
        return _FunctionalPipeline[Args](
            fn=fn,
            name=name,
            display_name=display_name or name,
            version=version,
            description=description,
        )

    return _decorate


class PipelineTest(unittest.TestCase):
    def test_pipeline_sink(self):
        from ..comps import component

        @component(name="amari.pipel.test.foo")
        def foo(x_num: int) -> None:
            raise RuntimeError("should not be called")

        @pipeline(name="amari.pipel.test.core")
        def ppl_core(x_num: int) -> None:
            foo(x_num * 2)
            foo(x_num * 3)

        @pipeline(name="amari.pipel.test.main")
        def ppl_main(x_num: int) -> None:
            ppl_core(x_num * 10)

        sink = BuiltComponentSink.create()
        ppl_main._build(4)
        built = sink.dump()
        self.assertEqual(len(built), 1)
        self.assertEqual(built[0].component.name, "amari.pipel.test.main")
        self.assertEqual(len(built[0].children), 1)
        sub = built[0].children[0]
        self.assertEqual(sub.component.name, "amari.pipel.test.core")
        self.assertEqual(len(sub.children), 2)
        children = sub.children
        self.assertEqual(children[0].component.name, "amari.pipel.test.foo")
        self.assertEqual(children[0].raw_kwargs, {"x_num": 80})
        self.assertEqual(children[1].component.name, "amari.pipel.test.foo")
        self.assertEqual(children[1].raw_kwargs, {"x_num": 120})

    pass
