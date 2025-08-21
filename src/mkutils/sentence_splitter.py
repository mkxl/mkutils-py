import dataclasses
from typing import ClassVar, Optional, Self

from mkutils.buffer import Buffer
from mkutils.utils import Utils


@dataclasses.dataclass(frozen=True, kw_only=True)
class SentenceSplitter:
    TERMINAL_PUNCTUATION: ClassVar[str] = ".?!"

    text_buffer: Buffer

    @classmethod
    def new(cls) -> Self:
        return cls(text_buffer=Buffer.empty())

    def push(self, *, text: str) -> Optional[str]:
        index = Utils.rfind(text=text, chars=self.TERMINAL_PUNCTUATION)

        if index is None:
            self.text_buffer.push_text(text)

            return None

        prefix, suffix = Utils.split(value=text, index=index + 1)

        self.text_buffer.push_text(prefix)

        sentence = self.text_buffer.pop_text()

        self.text_buffer.push_text(suffix)

        return sentence

    def pop(self) -> str:
        return self.text_buffer.pop_text()
