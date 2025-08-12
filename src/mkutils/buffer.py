import abc
import dataclasses
from typing import ClassVar, Optional, Protocol, Self


class Buffer[T](Protocol):
    @abc.abstractmethod
    def len(self) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def reset(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def value(self) -> T:
        raise NotImplementedError

    @abc.abstractmethod
    def push(self, value: T) -> None:
        raise NotImplementedError

    def is_empty(self) -> bool:
        return self.len() == 0

    def is_nonempty(self) -> bool:
        return not self.is_empty()

    def pop(self) -> T:
        value = self.value()

        self.reset()

        return value


@dataclasses.dataclass(frozen=True, kw_only=True)
class ByteBuffer(Buffer[bytes]):
    byte_str: bytearray

    @classmethod
    def new(cls) -> Self:
        return cls(byte_str=bytearray())

    def len(self) -> int:
        return len(self.byte_str)

    def reset(self) -> None:
        return self.byte_str.clear()

    def value(self) -> bytes:
        return bytes(self.byte_str)

    def push(self, value: bytes) -> None:
        self.byte_str.extend(value)

    def slice(self, *, begin: int, end: Optional[int]) -> bytes:
        byte_str = self.byte_str[begin:end]
        byte_str = bytes(byte_str)

        return byte_str


@dataclasses.dataclass(frozen=True, kw_only=True)
class StringBuffer(Buffer[str]):
    INITAL_LENGTH: ClassVar[int] = 0

    strings: list[str]
    length: int

    @classmethod
    def new(cls) -> Self:
        return cls(strings=[], length=cls.INITAL_LENGTH)

    def len(self) -> int:
        return self.length

    def reset(self) -> None:
        self.strings.clear()

        self.length = self.INITAL_LENGTH

    def value(self) -> str:
        return "".join(self.strings)

    def push(self, value: str) -> None:
        self.strings.append(value)

        self.length += len(value)
