import base64
import dataclasses
import datetime
import enum
import json
import pathlib
import unittest
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
)

import pydantic

from .defs import AzurePath, Field, ValidationError, _FieldInfo


@dataclasses.dataclass
class ParseDraft:
    fn_load_yaml: Callable[[Any], Any]
    fn_load_cli: Callable[[str], Any]
    fn_dump_yaml: Callable[[Any], Any]
    fn_dump_cli: Callable[[Any], str]
    fn_post_validate: Callable[[Any], Optional[str]]
    aml_type: str
    aml_min: Union[int, float, None] = None
    aml_max: Union[int, float, None] = None
    pass


@dataclasses.dataclass
class ParsedInputField:
    name: str
    docs: Optional[str]
    py_type: Any
    py_default: Any
    aml_optional: bool
    aml_default: Any
    draft: ParseDraft

    def is_input_field(self) -> bool:
        if isinstance(self.py_type, type) and issubclass(self.py_type, AzurePath):
            return self.py_type._PATH_IO == "input"
        return True

    pass


T = TypeVar("T")


def identity(x: T) -> T:
    return x


def parse_input_field(name: str, typ: Any, field: _FieldInfo) -> ParsedInputField:
    if shadow_typ := _is_optional(typ):
        # exception: string? cannot be null w/o defaults
        #            because the way AML treats them are as empty strings
        #            so we can only interpret them as empty strings
        if shadow_typ is str:
            raise ValidationError(f"Field `{name}` cannot be optional without default")
        # exception: T? cannot be required
        #            since there is no way to represent 'required null' in AML
        if field.default is ...:
            raise ValidationError(f"Field `{name}` cannot be a required optional")
        draft = _parse_draft(name, typ.__args__[0], field)
        _old_fn_load_yaml = draft.fn_load_yaml
        _old_fn_load_cli = draft.fn_load_cli
        draft.fn_load_yaml = lambda s: None if s is None else _old_fn_load_yaml(s)
        draft.fn_load_cli = lambda s: None if s == "" else _old_fn_load_cli(s)
        _old_fn_dump_yaml = draft.fn_dump_yaml
        _old_fn_dump_cli = draft.fn_dump_cli
        draft.fn_dump_yaml = lambda x: None if x is None else _old_fn_dump_yaml(x)
        draft.fn_dump_cli = lambda x: "" if x is None else _old_fn_dump_cli(x)
        aml_optional = True
    else:
        draft = _parse_draft(name, typ, field)
        aml_optional = False

    aml_default = None if field.default is ... else draft.fn_dump_yaml(field.default)
    return ParsedInputField(
        name=name,
        docs=field.docs,
        py_type=typ,
        py_default=field.default,
        aml_optional=aml_optional,
        aml_default=aml_default,
        draft=draft,
    )


def _is_optional(typ: Any) -> Optional[type]:
    origin = getattr(typ, "__origin__", None)
    if origin is Optional:
        return typ.__args__[0]
    if origin is not Union:
        return None
    args = typ.__args__
    if len(args) != 2:
        return None
    if args[0] is type(None):
        return args[1]
    if args[1] is type(None):
        return args[0]
    return None


def _parse_draft(name: str, typ: Any, field: _FieldInfo) -> ParseDraft:
    if typ is int:
        return ParseDraft(
            fn_load_yaml=identity,
            fn_load_cli=lambda s: int(s),
            fn_dump_yaml=identity,
            fn_dump_cli=lambda x: str(x),
            fn_post_validate=lambda x: (
                None
                if (field.min is None or x >= field.min)
                and (field.max is None or x <= field.max)
                else f"assert {field.min} <= x <= {field.max}"
            ),
            aml_type="integer",
            aml_min=field.min,
            aml_max=field.max,
        )
    elif typ is float:
        return ParseDraft(
            fn_load_yaml=identity,
            fn_load_cli=lambda s: json.loads(s),
            fn_dump_yaml=identity,
            fn_dump_cli=lambda x: json.dumps(x),
            fn_post_validate=lambda x: (
                None
                if (field.min is None or x >= field.min)
                and (field.max is None or x <= field.max)
                else f"assert {field.min} <= x <= {field.max}"
            ),
            aml_type="number",
            aml_min=field.min,
            aml_max=field.max,
        )
    elif typ is bool:
        return ParseDraft(
            fn_load_yaml=identity,
            fn_load_cli=lambda s: {"true": True, "false": False}[s.lower()],
            fn_dump_yaml=identity,
            fn_dump_cli=lambda x: {True: "true", False: "false"}[cast(bool, x)],
            fn_post_validate=lambda _: None,
            aml_type="boolean",
        )
    elif typ is str:
        return ParseDraft(
            fn_load_yaml=identity,
            fn_load_cli=identity,
            fn_dump_yaml=identity,
            fn_dump_cli=identity,
            fn_post_validate=lambda _: None,
            aml_type="string",
        )
    elif typ is bytes:
        return ParseDraft(
            fn_load_yaml=lambda s: base64.b64decode(s.encode()),
            fn_load_cli=lambda s: base64.b64decode(s.encode()),
            fn_dump_yaml=lambda s: base64.b64encode(cast(bytes, s)).decode(),
            fn_dump_cli=lambda s: base64.b64encode(cast(bytes, s)).decode(),
            fn_post_validate=lambda _: None,
            aml_type="string",
        )
    elif typ is datetime.datetime:
        return ParseDraft(
            fn_load_yaml=lambda s: datetime.datetime.fromisoformat(s),
            fn_load_cli=lambda s: datetime.datetime.fromisoformat(s),
            fn_dump_yaml=lambda x: cast(datetime.datetime, x).isoformat(),
            fn_dump_cli=lambda x: cast(datetime.datetime, x).isoformat(),
            fn_post_validate=lambda _: None,
            aml_type="string",
        )
    elif isinstance(typ, type) and issubclass(typ, enum.Enum):
        return ParseDraft(
            fn_load_yaml=lambda s: typ[s],
            fn_load_cli=lambda s: typ[s],
            fn_dump_yaml=lambda x: cast(enum.Enum, x).name,
            fn_dump_cli=lambda x: cast(enum.Enum, x).name,
            fn_post_validate=lambda _: None,
            aml_type="string",
        )
    elif isinstance(typ, type) and issubclass(typ, AzurePath):
        return ParseDraft(
            fn_load_yaml=lambda s: typ(location=pathlib.Path(s)),
            fn_load_cli=lambda s: typ(location=pathlib.Path(s)),
            fn_dump_yaml=lambda x: cast(AzurePath, x).location.as_posix(),
            fn_dump_cli=lambda x: cast(AzurePath, x).location.as_posix(),
            fn_post_validate=lambda _: None,
            aml_type="string",
        )

    # fallback process
    errs: List[str] = []
    _validate_serialize(typ, ["root"], errs)
    if errs:
        log = f"Field `{name}` has invalid type:\n"
        log += "\n".join(f"  {err}" for err in errs)
        raise ValidationError(log)
    Model = pydantic.create_model(f"parser[{name}]", value=(typ, ...))
    load_s = lambda s: Model(value=json.loads(s)).value  # type: ignore # noqa: E731
    dump_x = lambda x: json.dumps(  # noqa: E731
        json.loads(Model(value=x).model_dump_json())["value"],
        indent=None,
        ensure_ascii=True,
    )
    return ParseDraft(
        fn_load_yaml=load_s,
        fn_load_cli=load_s,
        fn_dump_yaml=dump_x,
        fn_dump_cli=dump_x,
        fn_post_validate=lambda _: None,
        aml_type="string",  # we using json
    )


def _validate_serialize(typ: Any, path: List[str], errs: List[str]) -> None:
    if typ in {int, float, bool, str, type(None)}:
        return
    elif typ in {datetime.datetime}:
        return

    origin = getattr(typ, "__origin__", None)
    if origin is list or origin is List:
        _validate_serialize(typ.__args__[0], path + ["i"], errs)
    elif origin is tuple or origin is Tuple:
        for i, t in enumerate(typ.__args__):
            _validate_serialize(t, path + [f"{i}"], errs)
    elif origin is dict or origin is Dict:
        _validate_serialize(typ.__args__[0], path + ["key"], errs)
        _validate_serialize(typ.__args__[1], path + ["value"], errs)
    elif origin is set or origin is Set:
        _validate_serialize(typ.__args__[0], path + ["i"], errs)
    elif origin is Union:
        for i, t in enumerate(typ.__args__):
            _validate_serialize(t, path + [f"{i}"], errs)
    elif origin is Optional:
        _validate_serialize(typ.__args__[0], path + ["t"], errs)
    elif origin is Literal:
        pass
    elif isinstance(typ, type) and issubclass(typ, pydantic.BaseModel):
        for name, field in typ.model_fields.items():
            _validate_serialize(field.annotation, path + [name], errs)
    elif isinstance(typ, type) and issubclass(typ, enum.Enum):
        for name, member in typ.__members__.items():
            if not isinstance(member.value, (int, str)):
                errs.append(f"invalid enum value `{name}` at: {'.'.join(path)}")
    else:
        errs.append(f"invalid type `{typ}` at: {'.'.join(path)}")
    return


class TypeCheckFmtTests(unittest.TestCase):
    def check(self, field: ParsedInputField, *values: Any) -> None:
        for value in values:
            self.assertEqual(
                field.draft.fn_load_yaml(field.draft.fn_dump_yaml(value)), value
            )
            self.assertEqual(
                field.draft.fn_load_cli(field.draft.fn_dump_cli(value)), value
            )
        pass

    def test_works(self) -> None:
        f_int = parse_input_field("f_int", int, Field(0))
        self.check(f_int, 0, 1, 2, 3)
        f_int_o = parse_input_field("f_int", Optional[int], Field(None))
        self.check(f_int_o, None, 1, 2, 3)
        f_float = parse_input_field("f_float", float, Field(0.0))
        self.check(f_float, 0.0, 1.0, 2.0, 3.0, 1e5)
        f_bool = parse_input_field("f_bool", bool, Field(False))
        self.check(f_bool, False, True)
        f_str = parse_input_field("f_str", str, Field(""))
        self.check(f_str, "", "a", "bc", "def")
        f_dt = parse_input_field("f_dt", Optional[datetime.datetime], Field(None))
        self.check(f_dt, None, datetime.datetime.now())
        f_bytes = parse_input_field("f_bytes", bytes, Field(...))
        self.check(f_bytes, b"", b"\xfe\xe1\xde\xad")

        class Option(enum.Enum):
            A = 1
            B = 2

        class Item(pydantic.BaseModel):
            name: str
            value: Option

        f_my_test = parse_input_field(
            "f_my_test", List[Item], Field([Item(name="a", value=Option.A)])
        )
        sample_1 = [Item(name="a", value=Option.A), Item(name="b", value=Option.B)]
        self.check(f_my_test, [], sample_1)

    pass
