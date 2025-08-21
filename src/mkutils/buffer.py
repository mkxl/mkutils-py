import dataclasses
from typing import Optional, Self

from mkutils.typing import ByteStr
from mkutils.utils import Utils


@dataclasses.dataclass(kw_only=True)
class Buffer:
    byte_array: bytearray

    @classmethod
    def from_byte_str(cls, byte_str: ByteStr) -> Self:
        byte_array = bytearray(byte_str)
        buffer = cls(byte_array=byte_array)

        return buffer

    @classmethod
    def empty(cls) -> Self:
        return cls.from_byte_str(b"")

    @classmethod
    def from_text(cls, text: str) -> Self:
        byte_str = Utils.byte_str(text=text)
        buffer = cls.from_byte_str(byte_str)

        return buffer

    def num_bytes(self) -> int:
        return len(self.byte_array)

    def byte_str(self) -> bytes:
        return bytes(self.byte_array)

    def text(self) -> str:
        return Utils.text(byte_str=self.byte_array)

    def push_text(self, text: str) -> None:
        byte_str = Utils.byte_str(text=text)

        self.push_byte_str(byte_str)

    def push_byte_str(self, byte_str: ByteStr) -> None:
        self.byte_array.extend(byte_str)

    def is_empty(self) -> bool:
        return self.num_bytes() == 0

    def is_nonempty(self) -> bool:
        return not self.is_empty()

    def slice(self, *, begin: int, end: Optional[int]) -> bytes:
        byte_array = self.byte_array[begin:end]
        byte_str = bytes(byte_array)

        return byte_str

    def pop_bytes_left(self, *, chunk_size: int) -> bytes:
        index = Utils.largest_multiple_leq(value=chunk_size, max_value=self.num_bytes())
        byte_array, self.byte_array = Utils.split(value=self.byte_array, index=index)
        byte_str = bytes(byte_array)

        return byte_str

    def pop_bytes(self) -> bytes:
        byte_str = self.byte_str()
        self.byte_array = bytearray()

        return byte_str

    def pop_text(self) -> str:
        return Utils.text(byte_str=self.pop_bytes())
