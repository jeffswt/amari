from typing_extensions import Never


def guard_never(_: Never) -> Never:
    raise RuntimeError("unreachable code")
