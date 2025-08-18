import abc
from collections.abc import AsyncIterator
from typing import Protocol

from mkutils import Audio


class Tts(Protocol):
    @abc.abstractmethod
    def aiter_audio(self) -> AsyncIterator[Audio]:
        raise NotImplementedError

    @abc.abstractmethod
    async def asend(self, *, text: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def aflush(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def aclose(self) -> None:
        raise NotImplementedError
