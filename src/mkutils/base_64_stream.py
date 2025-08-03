import dataclasses
from typing import ClassVar, Self

from mkutils.utils import Utils


@dataclasses.dataclass(kw_only=True)
class Base64Stream:
    INITIAL_CURSOR: ClassVar[int] = 0
    CHUNK_SIZE: ClassVar[int] = 3

    byte_str: bytearray
    cursor: int

    @classmethod
    def new(cls) -> Self:
        return cls(byte_str=bytearray(), cursor=cls.INITIAL_CURSOR)

    def length(self) -> int:
        return len(self.byte_str)

    def _extend(self, *, byte_str: bytes, finish: bool) -> str:
        self.byte_str.extend(byte_str)

        end = self.length() if finish else Utils.largest_multiple_leq(value=self.CHUNK_SIZE, max_value=self.length())
        byte_str = self.byte_str[self.cursor : end]
        base_64_str = Utils.b64encode(byte_str)
        self.cursor = end

        return base_64_str

    def extend(self, byte_str: bytes) -> str:
        return self._extend(byte_str=byte_str, finish=False)

    def finish(self) -> str:
        return self._extend(byte_str=b"", finish=True)
