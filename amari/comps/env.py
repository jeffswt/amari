import dataclasses
import enum
from typing import TYPE_CHECKING, Any, Dict, List, Union

from ..utils.pyctx import PyCtx

if TYPE_CHECKING:
    from ..comps import _FunctionalComponent
    from ..pipel import _FunctionalPipeline


class ComponentBuildEnv(enum.Enum):
    """Stores compiled component configs here for later use."""

    build = "build"
    """Preparing component for execution in a remote environment."""

    run = "run"
    """Executing component in local Python environment."""

    @classmethod
    def set(cls, value: "ComponentBuildEnv") -> None:
        _BuildEnvCtx.append(value, offset=1)

    @classmethod
    def get(cls) -> "ComponentBuildEnv":
        top = _BuildEnvCtx.get()
        return top[-1] if top else ComponentBuildEnv.run

    pass


_BuildEnvCtx: PyCtx["ComponentBuildEnv"] = PyCtx(
    key="amari.comps.env.ComponentBuildEnv"
)


@dataclasses.dataclass
class BuiltComponentConfig:
    # since the kwargs would be remembered & scheduled by a pipeline, here
    # we record everything in yaml and no positional args are kept
    component: Union["_FunctionalComponent", "_FunctionalPipeline"]
    # this must be in yaml format to be usable by shrike
    raw_kwargs: Dict[str, Any]

    # specific to pipelines: we have children
    children: List["BuiltComponentConfig"]
    pass


class BuiltComponentSink:
    """Stores compiled component & pipeline components' configs here for
    collecting and consumption."""

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
