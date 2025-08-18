import abc
import dataclasses
from collections.abc import AsyncIterator
from typing import Any, Protocol, Union

from mkutils.queue import EagerQueue

type LlmOutput = Union["TextChunk", "ToolCall"]


@dataclasses.dataclass(frozen=True, kw_only=True)
class ToolCall:
    name: str
    id: str
    arguments: str
    llm_input: Any


@dataclasses.dataclass(frozen=True, kw_only=True)
class TextChunk:
    text: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class LlmResponse:
    llm_output_eager_queue: EagerQueue[LlmOutput]


class Llm(Protocol):
    @abc.abstractmethod
    def append_user_message(self, user_message: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def append_assistant_message(self, assistant_message: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def append_tool_call(self, tool_call: ToolCall) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def append_tool_call_result(self, *, tool_call_id: str, result: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def aiter_llm_outputs(self) -> AsyncIterator[LlmOutput]:
        raise NotImplementedError

    def respond(self) -> LlmResponse:
        llm_output_eager_queue = EagerQueue.new(self.aiter_llm_outputs())
        llm_response = LlmResponse(llm_output_eager_queue=llm_output_eager_queue)

        return llm_response
