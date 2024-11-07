import enum

from ..utils.pyctx import PyCtx


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
