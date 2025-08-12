import dataclasses
from typing import ClassVar, Self

from mkutils.string_buffer import StringBuffer
from mkutils.utils import Utils


@dataclasses.dataclass(kw_only=True)
class Base64Stream:
    DEFAULT_EXTEND_FINISH: ClassVar[bool] = False
    INITIAL_CURSOR: ClassVar[int] = 0
    CHUNK_SIZE: ClassVar[int] = 3

    byte_str: bytearray
    string_buffer: StringBuffer
    cursor: int

    @classmethod
    def new(cls) -> Self:
        return cls(byte_str=bytearray(), string_buffer=StringBuffer.new(), cursor=cls.INITIAL_CURSOR)

    def length(self) -> int:
        return len(self.byte_str)

    def extend(self, byte_str: bytes, *, finish: bool = DEFAULT_EXTEND_FINISH) -> str:
        self.byte_str.extend(byte_str)

        end = self.length() if finish else Utils.largest_multiple_leq(value=self.CHUNK_SIZE, max_value=self.length())
        byte_str = self.byte_str[self.cursor : end]
        base64_str = Utils.b64encode(byte_str)
        self.cursor = end

        self.string_buffer.push(base64_str)

        return base64_str

    def finish(self) -> str:
        return self.extend(byte_str=b"", finish=True)

    def string(self) -> str:
        return self.string_buffer.string()
