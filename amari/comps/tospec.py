from types import EllipsisType
from typing import Any, TypeVar, Union

from ..typecheck.args import ParsedFunction
from ..typecheck.defs import AzurePath
from ..typecheck.fmt import ParsedInputField
from . import _FunctionalComponent


def extract_component_spec(entrypoint: str, cm: _FunctionalComponent) -> dict:
    """Generate AML-style component specifications."""

    component_spec = {
        "name": cm.name,
        "display_name": cm.display_name,
        "version": cm.version,
        "type": "spark",
        "tags": un_nullish(cm.tags),
        "description": un_nullish(cm.docs),
        "is_deterministic": cm.is_deterministic,
        "inputs": [_fmt_field(fd) for fd in cm.parsed_fn.fields if fd.is_input_field()],
        "outputs": [
            _fmt_field(fd) for fd in cm.parsed_fn.fields if not fd.is_input_field()
        ],
        "command": f"python {entrypoint} {_fmt_command_args(cm.parsed_fn)}",
        "environment": ...,
    }
    return un_no_null(component_spec)


def _fmt_field(fd: ParsedInputField) -> dict:
    var = {
        "type": fd.draft.aml_type,
        "optional": fd.aml_optional,
        "default": un_nullish(fd.aml_default),
        "description": fd.docs or fd.name,
        "min": un_nullish(fd.draft.aml_min),
        "max": un_nullish(fd.draft.aml_max),
        "datastore_mode": un_nullish(
            fd.py_type._PATH_DATASTORE_MODE
            if isinstance(fd.py_type, AzurePath)
            else None
        ),
    }
    return un_no_null(var)


def _fmt_command_args(fn: ParsedFunction) -> str:
    args = ""
    for field in fn.fields:
        io_kw = "input" if field.is_input_field() else "output"
        arg = "--{field.name} ${{" + io_kw + "." + field.name + "}}"
        if field.aml_optional:
            arg = "$[[" + arg + "]]"
        args += " " + arg
    return args.strip()


T = TypeVar("T")


def un_nullish(value: T) -> Union[T, EllipsisType]:
    if value is None:
        return ...
    return value


def un_no_null(value: Any) -> Any:
    if isinstance(value, list):
        return [un_no_null(v) for v in value if v is not ...]
    elif isinstance(value, dict):
        return {k: un_no_null(v) for k, v in value.items() if v is not ...}
    return value
