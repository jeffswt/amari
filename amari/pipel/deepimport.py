import ast
import unittest
from typing import Callable, Dict, List, Literal, Optional, Tuple, TypeAlias, cast

import black
import pydantic

SymbolName: TypeAlias = str

CodeBlock: TypeAlias = str


class ImportStatement(pydantic.BaseModel):
    """
    { module=['pydantic'], symbols=[], level=0 } ->
        import pydantic
    { module=[], symbols=[('numpy', 'np')], level=0 } ->
        import numpy as np
    { module=['itertools'], symbols=[], level=1 } ->
        from . import itertools
    { module=['pathlib'], symbols=[('Path', 'Path')], level=0 } ->
        from pathlib import Path
    { module=['runner', 'types'], symbols=[('Enum', 'En'), ('Struct', 'Struct')], level=2 } ->
        from ..runner.types import Enum as En, Struct
    """

    kind: Literal["import"]
    code: CodeBlock

    module: list[SymbolName]
    symbols: list[tuple[SymbolName, SymbolName]]
    level: int
    pass


def _parse_import_statement(
    code: CodeBlock, node: ast.Import | ast.ImportFrom
) -> ImportStatement:
    if isinstance(node, ast.Import):
        if len(node.names) == 0:
            raise SyntaxError("import statement has no targets")
        if len(node.names) != 1:
            raise SyntaxError(
                f"import statement has multiple targets: {ast.unparse(node)}"
            )
        name = node.names[0].name
        module = name.split(".")
        symbols = []
        if node.names[0].asname is not None:
            symbols.append((module.pop(), node.names[0].asname))
        return ImportStatement(
            kind="import",
            code=_prettify_code(code),
            module=module,
            symbols=symbols,
            level=0,
        )
    elif isinstance(node, ast.ImportFrom):
        return ImportStatement(
            kind="import",
            code=_prettify_code(code),
            module=[i for i in (node.module or "").split(".") if i],
            symbols=[(i.name, i.asname or i.name) for i in node.names],
            level=node.level or 0,
        )
    raise SyntaxError(f"unexpected import node: {ast.dump(node)}")


def _prettify_code(code: CodeBlock) -> CodeBlock:
    code = black.format_str(code, mode=black.Mode())
    return code


def _get_deep_import_paths(
    path: Tuple[str, ...],
    get_code: Callable[[Tuple[str, ...]], Optional[CodeBlock]],
    is_package: Callable[[str], bool],
) -> List[Tuple[str, ...]]:
    """Fetches paths of all transitive imports from a Python file."""

    code = get_code(path)
    if code is None:
        return []
    node = ast.parse(code)
    imports: List[ImportStatement] = []
    for stmt in node.body:
        if isinstance(stmt, ast.Import) or isinstance(stmt, ast.ImportFrom):
            imports.append(_parse_import_statement(code, stmt))

    result = [path]
    for imp in imports:
        if imp.level == 0:
            the_symbol = imp.module[0] if imp.module else imp.symbols[0][0]
            if is_package(the_symbol):
                continue
        child = tuple(list(path))
        if imp.level > 0:
            child = child[: -imp.level]
        child = child + tuple(imp.module)
        # 2 in case we miss files like `from . import foo``+
        result += _get_deep_import_paths(child, get_code, is_package)
        result += _get_deep_import_paths(child + ("__init__",), get_code, is_package)
        for sym in imp.symbols:
            result += _get_deep_import_paths(child + (sym[0],), get_code, is_package)
            result += _get_deep_import_paths(
                child + (sym[0], "__init__"), get_code, is_package
            )
    return result


class DeepImportParserTests(unittest.TestCase):
    def test_parse_import(self):
        def _test(
            code: CodeBlock,
            module: list[SymbolName],
            symbols: list[tuple[SymbolName, SymbolName]],
            level: int,
            alt_code: str | None = None,
        ):
            node = ast.parse(code)
            expected = ImportStatement(
                kind="import", code=code, module=module, symbols=symbols, level=level
            )
            parsed = _parse_import_statement(code, cast(ast.Import, node.body[0]))
            self.assertEqual(parsed, expected)

        _test("import pydantic\n", module=["pydantic"], symbols=[], level=0)
        _test("import pathlib.path\n", module=["pathlib", "path"], symbols=[], level=0)
        _test(
            "import pathlib.any.path as p\n",
            module=["pathlib", "any"],
            symbols=[("path", "p")],
            level=0,
            alt_code="from pathlib.any import path as p\n",
        )
        _test(
            "from pathlib import Path\n",
            module=["pathlib"],
            symbols=[("Path", "Path")],
            level=0,
        )
        _test(
            "from pathlib import Path as P\n",
            module=["pathlib"],
            symbols=[("Path", "P")],
            level=0,
        )
        _test("from . import foo\n", module=[], symbols=[("foo", "foo")], level=1)
        _test(
            "from ...utils.strings import bar, foobar as fb\n",
            module=["utils", "strings"],
            symbols=[("bar", "bar"), ("foobar", "fb")],
            level=3,
        )

    def test_deep_imports(self):
        paths: Dict[str, str] = {
            "src/run": "import numpy\nfrom . import foo\nfrom ..config import ConfigType\n",
            "src/foo": "import os\nfrom .. import main\n",
            "config/__init__": "from .types import ConfigType\n",
            "config/types": "import pydantic\n",
            "__init__": "from argparse import ArgumentParser\n",
            "misc/__main__": "import sys\n",
        }
        packages = {"numpy", "os", "pydantic", "argparse", "sys"}
        deep_imports = _get_deep_import_paths(
            path=("src", "run"),
            get_code=lambda path: paths.get("/".join(path), None),
            is_package=lambda symbol: symbol in packages,
        )
        expected = {
            "src/run",
            "src/foo",
            "config/__init__",
            "config/types",
            "__init__",
        }
        self.assertEqual(sorted("/".join(p) for p in deep_imports), sorted(expected))

    pass
