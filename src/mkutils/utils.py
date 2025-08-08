import asyncio
import base64
import functools
import textwrap
from asyncio import FIRST_COMPLETED, Future, Task
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Iterator
from typing import (
    Any,
    ClassVar,
    Optional,
    TypeGuard,
    Union,
)

import orjson
import yaml
from httpx import URL, HTTPError, Response
from pydantic import BaseModel, TypeAdapter, ValidationError

from mkutils.interval import Interval
from mkutils.time import Duration
from mkutils.typing import AsyncFunction, JsonObject, SyncFunction


class Shape:
    def __init__(self, *shape: str) -> None:
        self.shape = shape


# pylint: disable=too-many-public-methods
class Utils:
    ENCODING: ClassVar[str] = "utf-8"
    PYDANTIC_BASE_MODEL_DUMP_MODE: ClassVar[str] = "json"

    @staticmethod
    async def aconsume(value_iter: AsyncIterable[Any]) -> None:
        async for _value in value_iter:
            pass

    @staticmethod
    async def aintersperse[T](*, value_iter: AsyncIterable[T], filler: T) -> AsyncIterator[T]:
        async for value in value_iter:
            yield value
            yield filler

    # NOTE: inspired by [https://stackoverflow.com/a/62309083]
    @classmethod
    async def amerge[T](cls, *value_iters: AsyncIterable[T]) -> AsyncIterator[T]:
        value_iter_from_anext_task = {cls._anext_task(value_iter): value_iter for value_iter in map(aiter, value_iters)}

        while 0 < len(value_iter_from_anext_task):  # noqa: SIM300
            completed_tasks, _pending_tasks = await cls.await_first(*value_iter_from_anext_task.keys())

            for completed_task in completed_tasks:
                try:
                    yield completed_task.result()
                except StopAsyncIteration:
                    pass
                else:
                    value_iter = value_iter_from_anext_task[completed_task]
                    anext_task = cls._anext_task(value_iter)
                    value_iter_from_anext_task[anext_task] = value_iter
                finally:
                    value_iter_from_anext_task.pop(completed_task)

    @classmethod
    def _anext_task[T](cls, value_iter: AsyncIterable[T]) -> Task[T]:
        return cls.create_task(anext, value_iter)

    @staticmethod
    async def aonce[T](value: T) -> AsyncIterator[T]:
        yield value

    @staticmethod
    async def await_first[T](*awaitables: Awaitable[T]) -> tuple[set[Task[T]], set[Task[T]]]:
        # NOTE: can't use a generator here
        tasks = [
            awaitable if isinstance(awaitable, Task) else asyncio.create_task(awaitable) for awaitable in awaitables
        ]
        completed_tasks, _pending_tasks = pair = await asyncio.wait(tasks, return_when=FIRST_COMPLETED)

        for task in completed_tasks:
            exception = task.exception()

            if exception is not None:
                raise exception

        return pair

    @classmethod
    def b64encode(cls, byte_str: bytes) -> str:
        return base64.b64encode(byte_str).decode(encoding=cls.ENCODING)

    @staticmethod
    def create_task[**P, T](fn: AsyncFunction[P, T], *args: P.args, **kwargs: P.kwargs) -> Task[T]:
        coro = fn(*args, **kwargs)
        task = asyncio.create_task(coro)

        return task

    @staticmethod
    def dedent(text: str) -> str:
        text = text.lstrip("\n")
        text = textwrap.dedent(text)

        return text

    @staticmethod
    def ensure_string(string: Optional[str]) -> str:
        return "" if string is None else string

    # NOTE: make this an async method to ensure it's being called from an async context to ensure that
    # [asyncio.get_running_loop()] can run
    @staticmethod
    async def future[T]() -> Future[T]:
        # NOTE:
        # - prefer [asyncio.get_running_loop()] over [asyncio.get_event_loop] per
        #   [https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_event_loop]
        # - prefer [loop.create_future()] over [asyncio.Future()] per
        #   [https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_event_loop]
        return asyncio.get_running_loop().create_future()

    @staticmethod
    def iter_intervals(*, begin: int, total: int, chunk_size: int, exact: bool) -> Iterator[Interval[int]]:
        endpoint_range = range(begin, total, chunk_size)
        endpoint_iter = iter(endpoint_range)
        interval_begin = next(endpoint_iter, None)

        if interval_begin is None:
            return

        for endpoint in endpoint_iter:
            yield Interval[int](begin=interval_begin, end=endpoint)

            interval_begin = endpoint

        if not exact and interval_begin != total:
            yield Interval[int](begin=interval_begin, end=total)

    @staticmethod
    def is_not_none_and_is_nonempty(text: Optional[str]) -> TypeGuard[str]:
        return text is not None and text != ""

    @staticmethod
    def add_opt[T](left: Optional[T], right: Optional[T]) -> Optional[T]:
        if left is None:
            return right

        if right is None:
            return left

        return left + right  # ty: ignore[unsupported-operator]

    @classmethod
    def json_dump(cls, value: BaseModel) -> JsonObject:
        return value.model_dump(mode=cls.PYDANTIC_BASE_MODEL_DUMP_MODE)

    @classmethod
    def _json_dumps_default(cls, value: Any) -> Union[str, JsonObject]:
        if isinstance(value, BaseModel):
            return cls.json_dump(value)

        return str(value)

    # NOTE-17964d: use orjson because it's faster [https://github.com/ijl/orjson?tab=readme-ov-file#serialize]
    @classmethod
    def json_dumps(cls, json_obj: Optional[JsonObject] = None, **kwargs: Any) -> str:
        json_obj = kwargs if json_obj is None else (json_obj | kwargs)
        json_str = orjson.dumps(json_obj, default=cls._json_dumps_default).decode(cls.ENCODING)

        return json_str

    # NOTE-17964d
    @classmethod
    def json_loads(cls, json_str: str) -> Any:
        return orjson.loads(json_str)

    @staticmethod
    def keyed_by[T](*, attr: str) -> SyncFunction[type[T], type[T]]:
        def decorator(cls: type[T]) -> type[T]:
            def __str__(self) -> str:
                return getattr(self, attr)

            def __hash__(self) -> int:
                return hash(str(self))

            cls.__str__ = __str__
            cls.__hash__ = __hash__

            return cls

        return decorator

    @staticmethod
    def largest_multiple_leq(*, value: int, max_value: int) -> int:
        return (max_value // value) * value

    @staticmethod
    def model_validate_yaml[S: BaseModel](yaml_str: str, *, type_arg: type[S]) -> S:
        value = yaml.safe_load(yaml_str)
        base_model = TypeAdapter(type_arg).validate_python(value)

        return base_model

    # NOTE-17964d
    @staticmethod
    def try_validate_json_str[T](*, json_str: str, type_arg: type[T]) -> Union[T, str]:
        try:
            return TypeAdapter(type_arg).validate_json(json_str)
        except ValidationError:
            return json_str

    @classmethod
    async def araise_for_status(cls, *, response: Response) -> None:
        try:
            response.raise_for_status()
        except HTTPError as exc:
            response_byte_str = await response.aread()
            response_str = response_byte_str.decode(cls.ENCODING)
            response = cls.try_validate_json_str(json_str=response_str, type_arg=Any)
            value_error = cls.value_error(response=response)

            raise value_error from exc

    @staticmethod
    def to_sync_fn[T, **P](async_fn: AsyncFunction[P, T]) -> SyncFunction[P, T]:
        @functools.wraps(async_fn)
        def fn(*args: P.args, **kwargs: P.kwargs) -> T:
            coroutine = async_fn(*args, **kwargs)
            value = asyncio.run(coroutine)

            return value

        return fn

    @staticmethod
    def url(*, url: str, query_params: Optional[JsonObject]) -> str:
        url_obj = URL(url, params=query_params)
        url = str(url_obj)

        return url

    @classmethod
    def value_error(cls, **kwargs: Any) -> ValueError:
        error_str = cls.json_dumps(kwargs)
        value_error = ValueError(error_str)

        return value_error

    # NOTE: yield points: [https://tokio.rs/blog/2020-04-preemption]
    @staticmethod
    async def yield_now(*, seconds: float = Duration.DEFAULT_SECONDS) -> None:
        await Duration.new(seconds=seconds).sleep()
