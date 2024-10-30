# typecheck/defs: define additional types that would not have been supported by
#                 native Python annotations.

import dataclasses
from types import EllipsisType
from typing import Any, Literal, Optional, Union


class ValidationError(TypeError):
    pass


def Field(
    # generic
    default: Optional[Union[Any, EllipsisType]],  # default value or `...`
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
    default: Optional[Union[Any, EllipsisType]]
    docs: Optional[str]
    min: Optional[Union[int, float]]
    max: Optional[Union[int, float]]
    pass


class AzurePath:
    _PATH_IO: Literal["input", "output"] = "input"
    _PATH_DATASTORE_MODE: str = "hdfs"

    def __init__(self, location: str):
        self.__location = location

    @property
    def location(self) -> str:
        return self.__location

    pass


class InputPathFromHDFS(AzurePath):
    _PATH_IO = "input"
    _PATH_DATASTORE_MODE = "hdfs"
    pass


class OutputPathOnHDFS(AzurePath):
    _PATH_IO = "output"
    _PATH_DATASTORE_MODE = "hdfs"
    pass
