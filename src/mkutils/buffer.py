import abc
import dataclasses
from typing import ClassVar, Optional, Protocol, Self

from mkutils.utils import Utils


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


@dataclasses.dataclass(kw_only=True)
class ByteBuffer(Buffer[bytes]):
    DEFAULT_BYTE_STR: ClassVar[bytes] = b""

    byte_array: bytearray

    @classmethod
    def new(cls, *, byte_str: bytes = DEFAULT_BYTE_STR) -> Self:
        byte_array = bytearray(byte_str)
        byte_buffer = cls(byte_array=byte_array)

        return byte_buffer

    def len(self) -> int:
        return len(self.byte_array)

    def reset(self) -> None:
        return self.byte_array.clear()

    def value(self) -> bytes:
        return bytes(self.byte_array)

    def push(self, value: bytes) -> None:
        self.byte_array.extend(value)

    def slice(self, *, begin: int, end: Optional[int]) -> bytes:
        byte_array = self.byte_array[begin:end]
        byte_str = bytes(byte_array)

        return byte_str

    def pop_left(self, *, chunk_size: int) -> bytes:
        index = Utils.largest_multiple_leq(value=chunk_size, max_value=self.len())
        byte_array, self.byte_array = Utils.split(value=self.byte_array, index=index)
        byte_str = bytes(byte_array)

        return byte_str


@dataclasses.dataclass(kw_only=True)
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
