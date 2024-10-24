# typecheck/defs: define additional types that would not have been supported by
#                 native Python annotations.

import dataclasses
from typing import Any, Optional, Union


class ValidationError(TypeError):
    pass


def Field(
    # generic
    default: Optional[Any],  # default value or `...`
    docs: Optional[str] = None,
    # numbers
    min: Optional[Union[int, float]] = None,
    max: Optional[Union[int, float]] = None,
) -> Any:
    return _FieldInfo(
        default=default,
        docs=docs,
        min=min,
        max=max,
    )


@dataclasses.dataclass
class _FieldInfo:
    default: Optional[Any]
    docs: Optional[str]
    min: Optional[Union[int, float]]
    max: Optional[Union[int, float]]
    pass
