from collections.abc import Callable, Coroutine
from typing import Any, Union

type ByteStr = Union[bytes, bytearray]
type JsonObject = dict[str, Any]
type SyncFunction[X, Y] = Callable[[X], Y]
type AsyncFunction[X, Y] = SyncFunction[X, Coroutine[Any, Any, Y]]
type Function[X, Y] = Union[SyncFunction[X, Y], AsyncFunction[X, Y]]
type NestedList[T] = list[Any]
