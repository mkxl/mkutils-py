import dataclasses
from collections.abc import Iterable
from typing import Optional, Self


@dataclasses.dataclass(kw_only=True)
class StringBuffer:
    strings: list[str]
    length: int

    @classmethod
    def new(cls) -> Self:
        return cls(strings=[], length=0)

    def is_empty(self) -> bool:
        return self.length == 0

    def is_nonempty(self) -> bool:
        return not self.is_empty()

    def string(self, strings: Optional[Iterable[str]] = None) -> str:
        string_list = self.strings if strings is None else [*self.strings, *strings]
        joined_string = "".join(string_list)

        return joined_string

    def last(self) -> Optional[str]:
        return None if len(self.strings) == 0 else self.strings[-1]

    def push(self, string: str) -> None:
        self.strings.append(string)

        self.length += len(string)

    def pop(self) -> str:
        string = self.string()
        self.length = 0

        self.strings.clear()

        return string
