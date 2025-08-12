import dataclasses
from typing import ClassVar, Self

from mkutils.string_buffer import StringBuffer
from mkutils.utils import Utils


@dataclasses.dataclass(kw_only=True)
class B64Chunk:
    byte_str: bytes
    string: str

    @classmethod
    def new(cls, *, byte_str: bytes) -> Self:
        string = Utils.b64encode(byte_str)
        b64_chunk = cls(byte_str=byte_str, string=string)

        return b64_chunk


@dataclasses.dataclass(kw_only=True)
class B64Stream:
    DEFAULT_EXTEND_FINISH: ClassVar[bool] = False
    INITIAL_CURSOR: ClassVar[int] = 0
    CHUNK_SIZE: ClassVar[int] = 3

    byte_str: bytearray
    b64_string_buffer: StringBuffer
    cursor: int

    @classmethod
    def new(cls) -> Self:
        return cls(byte_str=bytearray(), b64_string_buffer=StringBuffer.new(), cursor=cls.INITIAL_CURSOR)

    def length(self) -> int:
        return len(self.byte_str)

    def extend(self, byte_str: bytes, *, finish: bool = DEFAULT_EXTEND_FINISH) -> B64Chunk:
        self.byte_str.extend(byte_str)

        end = self.length() if finish else Utils.largest_multiple_leq(value=self.CHUNK_SIZE, max_value=self.length())
        byte_str = self.byte_str[self.cursor : end]
        b64_chunk = B64Chunk.new(byte_str=byte_str)
        self.cursor = end

        self.b64_string_buffer.push(b64_chunk.string)

        return b64_chunk

    def finish(self) -> B64Chunk:
        return self.extend(byte_str=b"", finish=True)

    def string(self) -> str:
        return self.b64_string_buffer.string()
