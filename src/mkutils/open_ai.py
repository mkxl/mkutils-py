import dataclasses
from collections.abc import AsyncIterator
from http import HTTPMethod
from typing import Any, ClassVar, Literal, Optional, Self, Union

from pydantic import BaseModel

from mkutils.http import Http, HttpRequest
from mkutils.llm import Llm, LlmOutput, TextChunk, ToolCall
from mkutils.logger import Logger
from mkutils.typing import JsonObject
from mkutils.utils import Utils

logger: Logger = Logger.new(__name__)


class OutputTextDelta(BaseModel):
    TYPE: ClassVar[str] = "response.output_text.delta"

    type: Literal[TYPE]  # ty: ignore[invalid-type-form]
    delta: str

    def text_chunk(self) -> TextChunk:
        return TextChunk(text=self.delta)


class FunctionCallItem(BaseModel):
    TYPE: ClassVar[str] = "function_call"

    id: str
    type: Literal[TYPE]  # ty: ignore[invalid-type-form]
    status: str
    arguments: str
    call_id: str
    name: str

    def tool_call(self) -> ToolCall:
        return ToolCall(name=self.name, id=self.call_id, arguments=self.arguments, llm_input=self)


class FunctionCall(BaseModel):
    TYPE: ClassVar[str] = "response.output_item.done"

    type: Literal[TYPE]  # ty: ignore[invalid-type-form]
    item: FunctionCallItem

    def tool_call(self) -> ToolCall:
        return self.item.tool_call()


@dataclasses.dataclass(frozen=True, kw_only=True)
class OpenAi(Llm):
    URL: ClassVar[str] = "https://api.openai.com/v1/responses"
    TYPE_ARG: ClassVar[type[Any]] = Union[OutputTextDelta, FunctionCall, JsonObject]

    http_request: HttpRequest
    model: str
    input: list[JsonObject]
    tools: list[JsonObject]

    @classmethod
    def new(cls, *, http: Http, api_key: str, model: str, tools: Optional[list[JsonObject]]) -> Self:
        http_request = cls._http_request(http=http, api_key=api_key)
        open_ai = cls(http_request=http_request, model=model, input=[], tools=tools)

        return open_ai

    @classmethod
    def _http_request(cls, *, http: Http, api_key: str) -> HttpRequest:
        return HttpRequest.new(http=http, method=HTTPMethod.POST, url=cls.URL).bearer_auth(token=api_key)

    def append_user_message(self, user_message: str) -> None:
        self.input.append({"role": "user", "content": user_message})

    def append_assistant_message(self, assistant_message: str) -> None:
        self.input.append({"role": "assistant", "content": assistant_message})

    def append_tool_call(self, tool_call: ToolCall) -> None:
        self.input.append(tool_call.llm_input)

    def append_tool_call_result(self, *, tool_call_id: str, result: str) -> None:
        self.input.append({"type": "function_call_output", "call_id": tool_call_id, "output": result})

    def _content(self) -> str:
        return Utils.json_dumps({"model": self.model, "input": self.input, "tools": self.tools})

    # pylint: disable=invalid-overridden-method
    @logger.instrument()
    async def aiter_llm_outputs(self) -> AsyncIterator[LlmOutput]:
        async for response in self.http_request.with_content(self._content()).aiter_sse(type_arg=self.TYPE_ARG):
            match response:
                case OutputTextDelta() as output_text_delta:
                    yield output_text_delta.text_chunk()
                case FunctionCall() as function_call:
                    yield function_call.tool_call()
                case ignored_response:
                    logger.warning(ignored_response=ignored_response)
