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
class ChunkedByteBuffer:
    DEFAULT_EXTEND_FINISH: ClassVar[bool] = False
    INITIAL_CURSOR: ClassVar[int] = 0

    byte_buffer: ByteBuffer
    chunk_size: int
    cursor: int

    @classmethod
    def new(cls, *, chunk_size: int) -> Self:
        return cls(byte_buffer=ByteBuffer.new(), chunk_size=chunk_size, cursor=cls.INITIAL_CURSOR)

    def extend(self, byte_str: bytes, *, finish: bool = DEFAULT_EXTEND_FINISH) -> bytes:
        self.byte_buffer.push(byte_str)

        end = (
            self.byte_buffer.len()
            if finish
            else Utils.largest_multiple_leq(value=self.chunk_size, max_value=self.byte_buffer.len())
        )
        byte_str = self.byte_buffer.slice(begin=self.cursor, end=end)
        self.cursor = end

        return byte_str

    def finish(self) -> bytes:
        return self.extend(b"", finish=True)


@dataclasses.dataclass(kw_only=True)
class B64Stream:
    CHUNK_SIZE: ClassVar[int] = 3

    chunked_byte_buffer: ChunkedByteBuffer
    b64_string: StringBuffer

    @classmethod
    def new(cls) -> Self:
        chunked_byte_buffer = ChunkedByteBuffer.new(chunk_size=cls.CHUNK_SIZE)
        b64_stream = cls(chunked_byte_buffer=chunked_byte_buffer, b64_string=StringBuffer.new())

        return b64_stream

    def extend(self, byte_str: bytes, *, finish: bool = ChunkedByteBuffer.DEFAULT_EXTEND_FINISH) -> B64Chunk:
        byte_str = self.chunked_byte_buffer.extend(byte_str, finish=finish)
        b64_chunk = B64Chunk.new(byte_str=byte_str)

        self.b64_string.push(b64_chunk.string)

        return b64_chunk

    def finish(self) -> B64Chunk:
        return self.extend(b"", finish=True)

    def string(self) -> str:
        return self.b64_string.value()
