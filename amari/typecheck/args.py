import dataclasses
import datetime
import inspect
import unittest
from typing import Callable, List, Optional

from .defs import Field, ValidationError, _FieldInfo
from .fmt import ParsedInputField, parse_input_field


@dataclasses.dataclass
class ParsedFunction:
    name: str
    py_impl: Callable[..., None]
    fields: List[ParsedInputField]
    pass


def parse_function(fn: Callable[..., None]) -> ParsedFunction:
    name = fn.__name__
    all_annotations = inspect.get_annotations(fn)
    if all_annotations.get("return", ...) is not None:
        raise ValueError(f"Function `{name}` should return None")

    annotations = [(k, v) for k, v in all_annotations.items() if k != "return"]
    defaults = fn.__defaults__ or ()
    defaults = [...] * (len(annotations) - len(defaults)) + list(defaults)
    fields: List[ParsedInputField] = []
    errs: List[ValidationError] = []
    for (name, typ), default in zip(annotations, defaults):
        if isinstance(default, _FieldInfo):
            field = default
        else:
            field = Field(default)
        try:
            parsed = parse_input_field(name, typ, field)
            fields.append(parsed)
        except ValidationError as e:
            errs.append(e)

    if errs:
        log = f"Function `{name}` has validation errors in:"
        for err in errs:
            for line in str(err).split("\n"):
                log += f"\n  {line}"
        raise ValidationError(log)
    return ParsedFunction(
        name=name,
        py_impl=fn,
        fields=fields,
    )


class TypeCheckArgsTest(unittest.TestCase):
    def test_typecheck_args(self):
        def example_fn(
            whisky: int,
            brandy: Optional[datetime.datetime] = None,
            beer: str = "corona",
            rum: List[str] = ...,  # type: ignore
            wine: float = Field(..., min=0.0, max=1.0),
        ) -> None:
            return

        parse_function(example_fn)

        def bad_fn(
            apple: Optional[str],
            banana: List[List[bytes]] = [],
        ) -> None:
            return

        with self.assertRaises(ValidationError):
            parse_function(bad_fn)

    pass
