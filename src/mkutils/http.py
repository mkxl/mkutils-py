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


@dataclasses.dataclass(kw_only=True)
class Http:
    client: AsyncClient

    @classmethod
    @contextlib.asynccontextmanager
    async def acontext(cls) -> AsyncIterator[Self]:
        async with AsyncClient() as client:
            yield cls(client=client)


@dataclasses.dataclass(kw_only=True)
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

    @classmethod
    def new(cls, *, http: Http, method: HTTPMethod, url: str, query_params: Optional[JsonObject] = None) -> Self:
        url = Utils.url(url=url, query_params=query_params)
        http_request = cls(http=http, method=method, url=url, content=None, headers={})

        return http_request

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

    async def iter_lines(self) -> AsyncIterator[str]:
        async with self.stream() as response:
            async for line in response.aiter_lines():
                yield line

    async def iter_sse[T](self, *, type_arg: type[T]) -> AsyncIterator[T]:
        type_adapter = TypeAdapter(type_arg)

        async for raw_line in self.iter_lines():
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
