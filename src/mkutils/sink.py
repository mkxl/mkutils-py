import contextlib
from collections.abc import AsyncIterable
from typing import Protocol


class Sink[T](Protocol):
    async def asend(self, value: T) -> None:
        raise NotImplementedError

    async def aclose(self) -> None:
        raise NotImplementedError

    async def aconsume(self, value_iter: AsyncIterable[T]) -> None:
        # NOTE-eec4b0
        async with contextlib.aclosing(self):
            async for value in value_iter:
                await self.asend(value)
