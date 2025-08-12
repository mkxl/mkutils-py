import contextlib
import copy
import dataclasses
from collections.abc import AsyncIterator
from http import HTTPMethod
from typing import ClassVar, Optional, Self

from httpx import AsyncClient, Response
from pydantic import TypeAdapter, ValidationError

from mkutils.logger import Logger
from mkutils.typing import JsonObject
from mkutils.utils import Utils

logger: Logger = Logger.new(__name__)


@dataclasses.dataclass(frozen=True, kw_only=True)
class Http:
    client: AsyncClient

    @classmethod
    @contextlib.asynccontextmanager
    async def acontext(cls) -> AsyncIterator[Self]:
        async with AsyncClient() as client:
            yield cls(client=client)


@dataclasses.dataclass(frozen=True, kw_only=True)
class HttpRequest:
    HEADER_NAME_CONTENT_TYPE: ClassVar[str] = "content-type"
    HEADER_NAME_AUTHORIZATION: ClassVar[str] = "authorization"
    CONTENT_TYPE_APPLICATION_JSON: ClassVar[str] = "application/json"
    SSE_LINE_PREFIX: ClassVar[str] = "data:"
    SSE_TERMINAL_LINE: ClassVar[str] = "[DONE]"

    http: Http
    method: HTTPMethod
    url: str
    content: Optional[str]
    headers: JsonObject

    # pylint: disable=too-many-arguments
    @classmethod
    def new(
        cls,
        *,
        http: Http,
        method: HTTPMethod,
        url: str,
        query_params: Optional[JsonObject] = None,
        headers: Optional[JsonObject] = None,
    ) -> Self:
        url = Utils.url(url=url, query_params=query_params)

        if headers is None:
            headers = {}

        return cls(http=http, method=method, url=url, content=None, headers=headers)

    def content_type_application_json(self) -> Self:
        self.headers[self.HEADER_NAME_CONTENT_TYPE] = self.CONTENT_TYPE_APPLICATION_JSON

        return self

    def bearer_auth(self, *, token: str) -> Self:
        self.headers[self.HEADER_NAME_AUTHORIZATION] = f"Bearer {token}"

        return self

    def with_content(self, content: str) -> Self:
        return copy.replace(self, content=content)

    @contextlib.asynccontextmanager
    async def stream(self) -> AsyncIterator[Response]:
        async with self.http.client.stream(
            method=self.method, url=self.url, content=self.content, headers=self.headers
        ) as response:
            await Utils.araise_for_status(response=response)

            yield response

    async def aiter_byte_strs(self) -> AsyncIterator[bytes]:
        async with self.stream() as response:
            async for byte_str in response.aiter_bytes():
                yield byte_str

    async def aiter_lines(self) -> AsyncIterator[str]:
        async with self.stream() as response:
            async for line in response.aiter_lines():
                yield line

    async def aiter_sse[T](self, *, type_arg: type[T]) -> AsyncIterator[T]:
        type_adapter = TypeAdapter(type_arg)

        async for raw_line in self.aiter_lines():
            if not raw_line.startswith(self.SSE_LINE_PREFIX):
                continue

            line = raw_line.removeprefix(self.SSE_LINE_PREFIX).strip()

            if line == self.SSE_TERMINAL_LINE:
                break

            try:
                yield type_adapter.validate_json(line)
            except ValidationError as validation_error:
                logger.warning(iter_sse_raw_line=raw_line, validation_error=validation_error)
            else:
                logger.debug(iter_sse_raw_line=raw_line)
