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
F64 = Type("f64")
BOOL = Type("bool")
STR = Type("str")
VOID = Type("void")


BUILTINS = {
    "i32": I32,
    "f64": F64,
    "bool": BOOL,
    "str": STR,
    "void": VOID,
}


def channel(inner: Type) -> Type:
    return Type("Chan", (inner,))


def array(inner: Type) -> Type:
    return Type("Array", (inner,))


def ptr(inner: Type) -> Type:
    return Type("Ptr", (inner,))


def const_ptr(inner: Type) -> Type:
    return Type("ConstPtr", (inner,))


def func(params: list[Type], ret: Type) -> Type:
    return Type("Func", tuple(params + [ret]))


def type_var(name: str) -> Type:
    return Type(f"${name}")


def is_type_var(ty: Type) -> bool:
    return ty.name.startswith("$")
