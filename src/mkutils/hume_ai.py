import dataclasses
from collections.abc import AsyncIterator
from http import HTTPMethod
from typing import ClassVar, Optional, Self

from pydantic import BaseModel

from mkutils.audio import Audio, AudioFormat, AudioInfo
from mkutils.buffer import Buffer
from mkutils.http import Http, HttpRequest
from mkutils.logger import Logger
from mkutils.queue import Queue
from mkutils.tts import Tts
from mkutils.utils import Utils

logger: Logger = Logger.new(__name__)


class Chunk(BaseModel):
    generation_id: str
    audio: str


@dataclasses.dataclass
class HumeAi(Tts):
    AUDIO_FORMAT: ClassVar[AudioFormat] = AudioFormat.PCM_S16LE
    AUDIO_INFO: ClassVar[AudioInfo] = AudioInfo(sample_rate=48_000, num_channels=1)
    CHUNK_SIZE = AUDIO_FORMAT.value.pcm_sample_width_with(default=1)
    HEADER_NAME_API_KEY: ClassVar[str] = "x-hume-api-key"
    MIN_AUDIO_BYTE_STR_LENGTH: ClassVar[int] = 2**10
    URL: ClassVar[str] = "https://api.hume.ai/v0/tts/stream/json"
    TERMINAL_PUNCTUATION: ClassVar[str] = ".?!"

    base_http_request: HttpRequest
    text_queue: Queue[str]
    text_buffer: Buffer
    voice_name: str

    @classmethod
    def new(cls, *, http: Http, api_key: str, voice_name: str) -> Self:
        base_http_request = cls._base_http_request(http=http, api_key=api_key)
        hume_ai = cls(
            base_http_request=base_http_request,
            text_queue=Queue.new(),
            text_buffer=Buffer.empty(),
            voice_name=voice_name,
        )

        return hume_ai

    @classmethod
    def _base_http_request(cls, *, http: Http, api_key: str) -> HttpRequest:
        headers = {cls.HEADER_NAME_API_KEY: api_key}
        base_http_request = HttpRequest.new(http=http, method=HTTPMethod.POST, url=cls.URL, headers=headers)

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
        byte_str_buffer = Buffer.empty()
        context_generation_id = None

        async for text in self.text_queue:
            content = self._content(text=text, context_generation_id=context_generation_id)
            http_request = self.base_http_request.with_content(content)

            async for line in http_request.aiter_lines():
                chunk = Chunk.model_validate_json(line)
                byte_str = Utils.b64decode(chunk.audio)
                context_generation_id = chunk.generation_id

                byte_str_buffer.push_byte_str(byte_str)

                if self.MIN_AUDIO_BYTE_STR_LENGTH <= byte_str_buffer.num_bytes():  # noqa: SIM300
                    byte_str = byte_str_buffer.pop_bytes_left(chunk_size=self.CHUNK_SIZE)

                    yield self._audio(byte_str=byte_str)

    # TODO: more sophisticated sentence splitting implementation
    async def asend(self, *, text: str) -> None:
        index = Utils.rfind(text=text, chars=self.TERMINAL_PUNCTUATION)

        if index is None:
            self.text_buffer.push_text(text)

            return

        prefix, suffix = Utils.split(value=text, index=index)

        self.text_buffer.push_text(prefix)

        await self.aflush()

        self.text_buffer.push_text(suffix)

    async def aflush(self) -> None:
        text = self.text_buffer.pop_text()

        if text != "":
            self.text_queue.append(text)

    async def aclose(self) -> None:
        await self.text_queue.aclose()
