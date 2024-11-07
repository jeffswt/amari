import copy
from typing import Any, Dict, List, Tuple

from ..typecheck.args import ParsedFunction


def fn_kwargs_from_py(
    name: str,
    parsed_fn: ParsedFunction,
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate positional and keyword arguments from Python function call into
    a dictionary of kwargs."""

    values: Dict[str, Any] = {}
    for i, field in enumerate(parsed_fn.fields):
        if i < len(args):
            value = args[i]
        elif field.name in kwargs:
            value = kwargs[field.name]
        else:
            if field.py_default is ...:
                raise TypeError(
                    f"{name}() missing required positional argument: '{field.name}'"
                )
            value = copy.deepcopy(field.py_default)

        validation_err = field.draft.fn_post_validate(value)
        if validation_err:
            raise ValueError(f"invalid value for '{field.name}': {validation_err}")
        values[field.name] = value

    return values


def fn_kwargs_from_yaml(
    parsed_fn: ParsedFunction,
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    """Get Python kwargs from an AML-ish configuration."""

    result: Dict[str, Any] = {}
    for field in parsed_fn.fields:
        key = field.name
        if key in kwargs:
            value = field.draft.fn_load_yaml(kwargs[key])
        else:
            value = copy.deepcopy(field.py_default)
        validation_err = field.draft.fn_post_validate(value)
        if validation_err:
            raise ValueError(f"invalid value for '{key}': {validation_err}")
        result[key] = value

    return result


def fn_kwargs_into_yaml(
    parsed_fn: ParsedFunction, kwargs: Dict[str, Any]
) -> Dict[str, Any]:
    """Convert Python kwargs into an AML-ish configuration so that they can be
    accepted by Pipeline builders."""

    fields = {field.name: field for field in parsed_fn.fields}
    result: Dict[str, Any] = {}
    for key, value in kwargs.items():
        if key not in fields:
            raise KeyError(f"unknown field '{key}'")
        field = fields[key]
        raw_value = field.draft.fn_dump_yaml(value)
        result[key] = raw_value
    return result


def fn_kwargs_from_cli(
    parsed_fn: ParsedFunction,
    argv: List[str],
) -> Dict[str, Any]:
    """Validate command-line arguments into a dictionary of kwargs."""

    fields = {field.name: field for field in parsed_fn.fields}
    # obtain
    raw_kwargs: Dict[str, str] = {}
    for i in range(0, len(argv), 2):
        raw_key = argv[i]
        if not raw_key.startswith("--"):
            raise KeyError(f"invalid option '{raw_key}'")
        if i + 1 >= len(argv):
            raise ValueError(f"missing value for '{raw_key}'")
        raw_value = argv[i + 1]
        key = raw_key[2:]
        if key not in fields:
            raise KeyError(f"unknown option '{raw_key}'")
        raw_kwargs[key] = raw_value

    # evaluate & assign
    kwargs: Dict[str, Any] = {}
    for key, field in fields.items():
        if key in raw_kwargs:
            raw_value = raw_kwargs[key]
            value = field.draft.fn_load_cli(raw_value)
        else:
            value = copy.deepcopy(field.py_default)
        validation_err = field.draft.fn_post_validate(value)
        if validation_err:
            raise ValueError(f"invalid value for '--{key}': {validation_err}")
        kwargs[key] = value

    return kwargs
