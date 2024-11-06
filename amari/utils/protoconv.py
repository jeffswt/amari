import unittest
from typing import Any, Dict, Type, cast, get_type_hints

import pydantic
from typing_extensions import Protocol, get_protocol_members, is_protocol


def protocol_as_base_model(proto: Type[Any]) -> Type[pydantic.BaseModel]:
    if not is_protocol(proto):
        raise TypeError(
            f"{proto.__name__} is not a Protocol. Did you remember to inherit (directly) from Protocol?"
        )
    type_hints = get_type_hints(proto)  # fields only
    members = list(get_protocol_members(proto))  # fields & methods
    if len(members) > len(type_hints):
        method_keys = ", ".join(sorted(set(members) - set(type_hints)))
        raise TypeError(
            f"unexpected abstract methods in {proto.__name__}: {method_keys}"
        )
    fields = {k: (v, ...) for k, v in type_hints.items()}
    model = pydantic.create_model(proto.__name__, **cast(Any, fields))
    return model


class ProtoConvTests(unittest.TestCase):
    def test_base_model_cast(self):
        class BaseProto(Protocol):
            x: Dict[str, int]
            y: bool | None

        class DerivedProto(BaseProto, Protocol):
            z: str

        DP = protocol_as_base_model(DerivedProto)

        _dp_ok = DP(x={"a": 1}, y=True, z="foo")
        self.assertRaises(pydantic.ValidationError, DP, x={"a": 1}, z="foo")
        self.assertRaises(pydantic.ValidationError, DP, x={"a": 1}, y=True)
        _dp_also_ok = DP(x={"a": 1}, y=True, z="foo", w=1)

        # you cannot have abstract methods in a basemodel-derivable protocol
        class BadBaseProto(Protocol):
            x: int

            def foo(self) -> None:
                pass

        class BadDerivedProto(BadBaseProto, Protocol):
            y: str

        self.assertRaises(TypeError, protocol_as_base_model, BadDerivedProto)

    pass
