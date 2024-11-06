import dataclasses
import inspect
import unittest
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclasses.dataclass
class PyCtxPointer(Generic[T]):
    ancestors: list[T]
    current: tuple[T] | None
    pass


class PyCtx(Generic[T]):
    def __init__(self, key: str):
        self._root_key = "__$__GENERIC_STORE__$__"
        self._key = key

    def get(self, offset: int = 0) -> list[T]:
        ptr, _off = self.__load(2 + offset)
        ret = list(ptr.ancestors)
        if ptr.current is not None:
            ret.append(ptr.current[0])
        return ret

    def append(self, value: T, offset: int = 0) -> None:
        ptr, off = self.__load(2 + offset)
        tmp = list(ptr.ancestors)
        if off > 0 and ptr.current is not None:
            tmp.append(ptr.current[0])
        new_ptr = PyCtxPointer(ancestors=tmp, current=(value,))
        self.__store(2 + offset, new_ptr)
        return

    def __load(self, offset: int) -> tuple[PyCtxPointer[T], int]:
        stk = inspect.stack()
        pointer = PyCtxPointer[T](ancestors=[], current=None)
        res_offset = 0
        # for frame in stk:
        for i, frame in enumerate(stk[offset:]):
            vars = frame.frame.f_locals
            if self._root_key not in vars:
                continue
            root: dict[str, PyCtxPointer[T]] = vars[self._root_key]
            if self._key not in root:
                continue
            pointer = root[self._key]
            res_offset = i
            break
        return pointer, res_offset

    def __store(self, offset: int, ptr: PyCtxPointer[T]) -> None:
        stk = inspect.stack()
        if len(stk) < offset:
            return
        frame = stk[offset].frame
        vars = frame.f_locals
        if self._root_key not in vars:
            vars[self._root_key] = {}
        root: dict[str, PyCtxPointer[T]] = vars[self._root_key]
        root[self._key] = ptr
        return

    pass


class PyCtxTests(unittest.TestCase):
    def test_working(self):
        """
        > [ a ] ---+-->   b   ------> [ c ] ------> [ d ]
        >  ^^^     |     ^^^           ^^^
        >          +----------------> [[e]] ------> [ f ]
        """
        import asyncio

        ctx = PyCtx[str]("test_working")
        result: list[list[str]] = []

        async def a() -> None:
            result.append(ctx.get())
            ctx.append("AAA")
            result.append(ctx.get())
            await b()
            result.append(ctx.get())
            e()
            result.append(ctx.get())

        async def b() -> None:
            result.append(ctx.get())
            await c()
            result.append(ctx.get())

        async def c() -> None:
            result.append(ctx.get())
            ctx.append("CCC")
            result.append(ctx.get())
            d()
            result.append(ctx.get())

        def d() -> None:
            result.append(ctx.get())
            ctx.append("DDD")
            result.append(ctx.get())

        def e() -> None:
            result.append(ctx.get())
            ctx.append("EEE")
            result.append(ctx.get())
            ctx.append("EEE")
            result.append(ctx.get())
            f()
            result.append(ctx.get())

        def f() -> None:
            result.append(ctx.get())
            ctx.append("FFF")
            result.append(ctx.get())

        expected: list[list[str]] = [
            [],  # a_0
            ["AAA"],  # a_1
            ["AAA"],  # b_0
            ["AAA"],  # c_0
            ["AAA", "CCC"],  # c_1
            ["AAA", "CCC"],  # d_0
            ["AAA", "CCC", "DDD"],  # d_1
            ["AAA", "CCC"],  # c_2
            ["AAA"],  # b_1
            ["AAA"],  # a_2
            ["AAA"],  # e_0
            ["AAA", "EEE"],  # e_1
            ["AAA", "EEE"],  # e_2
            ["AAA", "EEE"],  # f_0
            ["AAA", "EEE", "FFF"],  # f_1
            ["AAA", "EEE"],  # e_3
            ["AAA"],  # a_3
        ]
        asyncio.run(a())
        self.assertEqual(result, expected)

    pass
