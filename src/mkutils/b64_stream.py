import dataclasses
from typing import ClassVar, Self

from mkutils.buffer import ByteBuffer, StringBuffer
from mkutils.utils import Utils


@dataclasses.dataclass(frozen=True, kw_only=True)
class B64Chunk:
    byte_str: bytes
    string: str

    @classmethod
    def new(cls, *, byte_str: bytes) -> Self:
        string = Utils.b64encode(byte_str)
        b64_chunk = cls(byte_str=byte_str, string=string)

        return b64_chunk


@dataclasses.dataclass(frozen=True, kw_only=True)
class B64Stream:
    DEFAULT_EXTEND_FINISH: ClassVar[bool] = False
    INITIAL_CURSOR: ClassVar[int] = 0
    CHUNK_SIZE: ClassVar[int] = 3

    byte_buffer: ByteBuffer
    b64_string: StringBuffer
    cursor: int

    @classmethod
    def new(cls) -> Self:
        return cls(byte_buffer=ByteBuffer.new(), b64_string=StringBuffer.new(), cursor=cls.INITIAL_CURSOR)

    def len(self) -> int:
        return self.byte_buffer.len()

    def extend(self, byte_str: bytes, *, finish: bool = DEFAULT_EXTEND_FINISH) -> B64Chunk:
        self.byte_buffer.push(byte_str)

        end = self.len() if finish else Utils.largest_multiple_leq(value=self.CHUNK_SIZE, max_value=self.len())
        byte_str = self.byte_buffer.slice(begin=self.cursor, end=end)
        b64_chunk = B64Chunk.new(byte_str=byte_str)
        self.cursor = end

        self.b64_string.push(b64_chunk.string)

        return b64_chunk

    def finish(self) -> B64Chunk:
        return self.extend(b"", finish=True)

    def string(self) -> str:
        return self.b64_string.value()
