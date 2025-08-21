import dataclasses
from collections.abc import AsyncIterator
from http import HTTPMethod
from typing import ClassVar, Optional, Self

from pydantic import BaseModel

from mkutils.audio import Audio, AudioFormat, AudioInfo
from mkutils.http import Http, HttpRequest
from mkutils.logger import Logger
from mkutils.queue import Queue
from mkutils.sentence_splitter import SentenceSplitter
from mkutils.tts import Tts
from mkutils.utils import Utils

logger: Logger = Logger.new(__name__)


class Chunk(BaseModel):
    generation_id: str
    audio: str

    def byte_str(self) -> bytes:
        return Utils.b64decode(self.audio)


@dataclasses.dataclass
class HumeAi(Tts):
    AUDIO_FORMAT: ClassVar[AudioFormat] = AudioFormat.PCM_S16LE
    AUDIO_INFO: ClassVar[AudioInfo] = AudioInfo(sample_rate=48_000, num_channels=1)

    base_http_request: HttpRequest
    text_queue: Queue[str]
    sentence_splitter: SentenceSplitter
    voice_name: str

    @classmethod
    def new(cls, *, http: Http, api_key: str, voice_name: str) -> Self:
        base_http_request = cls._base_http_request(http=http, api_key=api_key)
        hume_ai = cls(
            base_http_request=base_http_request,
            text_queue=Queue.new(),
            sentence_splitter=SentenceSplitter.new(),
            voice_name=voice_name,
        )

        return hume_ai

    @classmethod
    def _base_http_request(cls, *, http: Http, api_key: str) -> HttpRequest:
        headers = {"x-hume-api-key": api_key}
        base_http_request = HttpRequest.new(
            http=http, method=HTTPMethod.POST, url="https://api.hume.ai/v0/tts/stream/json", headers=headers
        )

        return base_http_request

    def _content(self, *, text: str, context_generation_id: Optional[str]) -> str:
        json_obj = {
            "utterances": [{"text": text, "voice": {"provider": "HUME_AI", "name": self.voice_name}}],
            "instant_mode": True,
            "strip_headers": True,
            "format": {"type": "pcm"},
        }

        if context_generation_id is not None:
            json_obj["context"] = {"generation_id": context_generation_id}

        return Utils.json_dumps(json_obj)

    @classmethod
    def _audio(cls, *, byte_str: bytes) -> Audio:
        return Audio.new(byte_str=byte_str, audio_format=cls.AUDIO_FORMAT, audio_info=cls.AUDIO_INFO)

    # pylint: disable=invalid-overridden-method
    async def aiter_audio(self) -> AsyncIterator[Audio]:
        context_generation_id = None

        async for text in self.text_queue:
            content = self._content(text=text, context_generation_id=context_generation_id)
            http_request = self.base_http_request.with_content(content)

            async for line in http_request.aiter_lines():
                chunk = Chunk.model_validate_json(line)
                audio = self._audio(byte_str=chunk.byte_str())
                context_generation_id = chunk.generation_id

                yield audio

    def _append_text_to_queue(self, *, text: str) -> None:
        if text != "":
            self.text_queue.append(text)

    # TODO: more sophisticated sentence splitting implementation
    async def asend(self, *, text: str) -> None:
        match self.sentence_splitter.push(text=text):
            case str(sentence):
                self._append_text_to_queue(text=sentence)

    async def aflush(self) -> None:
        self._append_text_to_queue(text=self.sentence_splitter.pop())

    async def aclose(self) -> None:
        await self.text_queue.aclose()
