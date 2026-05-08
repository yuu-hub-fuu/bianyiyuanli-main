from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class Type:
    name: str
    params: tuple[Type, ...] = field(default_factory=tuple)

    def __str__(self) -> str:
        if not self.params:
            return self.name
        return f"{self.name}[{', '.join(map(str, self.params))}]"


I32 = Type("i32")
I64 = Type("i64")
F64 = Type("f64")
BOOL = Type("bool")
STR = Type("str")
VOID = Type("void")
JSON = Type("JsonValue")
TCP_STREAM = Type("TcpStream")
TCP_LISTENER = Type("TcpListener")
RANGE = Type("Range")


BUILTINS = {
    "i32": I32,
    "i64": I64,
    "f64": F64,
    "bool": BOOL,
    "str": STR,
    "void": VOID,
    "JsonValue": JSON,
    "TcpStream": TCP_STREAM,
    "TcpListener": TCP_LISTENER,
    "Range": RANGE,
}


def channel(inner: Type) -> Type:
    return Type("Chan", (inner,))


def array_type(inner: Type, size: int) -> Type:
    return Type("Array", (inner, Type(str(size))))


def array_any(inner: Type) -> Type:
    return Type("Array", (inner, Type("*")))


def dict_type(key: Type, value: Type) -> Type:
    return Type("Dict", (key, value))


def fn_type(params: list[Type], ret: Type) -> Type:
    return Type("Fn", tuple(params + [ret]))


def type_var(name: str) -> Type:
    return Type(f"${name}")


def is_type_var(ty: Type) -> bool:
    return ty.name.startswith("$")
