import copy
from typing import Any, Dict, List, Tuple

from . import _FunctionalComponent


def call_component(
    cm: _FunctionalComponent,
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> None:
    values: Dict[str, Any] = {}
    for i, field in enumerate(cm.parsed_fn.fields):
        if i < len(args):
            # value = args[i]
            pass
        elif field.name in kwargs:
            value = kwargs[field.name]
            values[field.name] = value
        else:
            if field.py_default is ...:
                raise TypeError(
                    f"{cm.display_name}() missing required positional argument: '{field.name}'"
                )
            value = copy.deepcopy(field.py_default)
            values[field.name] = value
    ret = cm.fn(*args, **values)
    return ret


def cli_run_component(
    cm: _FunctionalComponent,
    argv: List[str],
) -> None:
    fields = {field.name: field for field in cm.parsed_fn.fields}
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
    cm.fn(**kwargs)
    return
