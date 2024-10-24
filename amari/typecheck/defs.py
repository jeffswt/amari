# typecheck/defs: define additional types that would not have been supported by
#                 native Python annotations.

from typing import Any, Optional, Union


class Field:
    def __init__(
        self,
        # generic
        default: Optional[Any],  # default value or `...`
        docs: Optional[str] = None,
        # numbers
        min: Optional[Union[int, float]] = None,
        max: Optional[Union[int, float]] = None,
    ):
        self.default = default
        self.docs = docs
        self.min = min
        self.max = max

    @staticmethod
    def _default_field() -> "Field":
        return Field(default=...)

    pass
