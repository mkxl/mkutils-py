import asyncio
import contextlib
import dataclasses
from collections.abc import AsyncIterator
from typing import Annotated, ClassVar, Optional, Self

import websockets.asyncio.client
from pydantic import BaseModel, Field
from websockets.asyncio.client import ClientConnection

from mkutils.audio import Audio, AudioFormat, AudioInfo
from mkutils.tts import Tts
from mkutils.typing import JsonObject
from mkutils.utils import Utils


class AudioOutput(BaseModel):
    VALIDATION_ALIAS_IS_FINAL: ClassVar[str] = "isFinal"

    audio: Optional[str] = None
    is_final: Annotated[Optional[bool], Field(validation_alias=VALIDATION_ALIAS_IS_FINAL)] = None

    def byte_str(self) -> bytes:
        return Utils.b64decode(self.audio)


@dataclasses.dataclass(kw_only=True)
class ElevenLabs(Tts):
    AITER_AUDIO_TIMEOUT_DELAY_SECS: ClassVar[float] = 1.0

    eleven_labs_websocket: "ElevenLabsWebsocket"
    aiter_audio_timeout_delay_secs: Optional[float]

    @classmethod
    def new(cls, *, eleven_labs_websocket: "ElevenLabsWebsocket") -> Self:
        return cls(eleven_labs_websocket=eleven_labs_websocket, aiter_audio_timeout_delay_secs=None)

    # pylint: disable=invalid-overridden-method
    async def aiter_audio(self) -> AsyncIterator[Audio]:
        # NOTE: eleven labs gives no indication that all the generated speech for a given set of input messages has
        # been sent over, so to get around this, once self.aclose() has been called, we wait a set amount of time after
        # each received audio message for the next one to come before ending the iteration here
        while True:
            try:
                async with asyncio.timeout(self.aiter_audio_timeout_delay_secs):
                    yield await self.eleven_labs_websocket.anext_audio()
            except TimeoutError:
                break

    async def asend(self, *, text: str) -> None:
        await self.eleven_labs_websocket.asend(text=text, try_trigger_generation=False)

    async def aflush(self) -> None:
        await self.eleven_labs_websocket.asend(text=" ", try_trigger_generation=True)

    async def aclose(self) -> None:
        self.aiter_audio_timeout_delay_secs = self.AITER_AUDIO_TIMEOUT_DELAY_SECS


@dataclasses.dataclass(frozen=True, kw_only=True)
class ElevenLabsWebsocket:
    AUDIO_FORMAT: ClassVar[Optional[AudioFormat]] = AudioFormat.PCM_S16LE
    AUDIO_INFO: ClassVar[Optional[AudioInfo]] = AudioInfo(sample_rate=16_000, num_channels=1)
    HEADER_NAME_API_KEY: ClassVar[str] = "xi-api-key"
    MAX_SIZE: ClassVar[int] = 2**24
    QUERY_PARAMS: ClassVar[JsonObject] = {
        "output_format": "pcm_16000",
        "inactivity_timeout": 180,
        "model_id": "eleven_flash_v2_5",
    }

    websocket: ClientConnection

    # pylint: disable=unused-argument
    @classmethod
    @contextlib.asynccontextmanager
    async def acontext(cls, *, api_key: str, voice_id: str) -> AsyncIterator[Self]:
        async with cls._websocket(api_key=api_key, voice_id=voice_id) as websocket:
            eleven_labs = cls(websocket=websocket)

            await eleven_labs._init()

            yield eleven_labs

    @classmethod
    @contextlib.asynccontextmanager
    async def _websocket(cls, *, api_key: str, voice_id: str) -> AsyncIterator[ClientConnection]:
        url = f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input"
        uri = Utils.url(url=url, query_params=cls.QUERY_PARAMS)
        additional_headers = {cls.HEADER_NAME_API_KEY: api_key}
        websocket_cm = websockets.asyncio.client.connect(
            uri=uri, additional_headers=additional_headers, max_size=cls.MAX_SIZE
        )

        async with websocket_cm as websocket:
            yield websocket

    async def asend(self, *, text: str, try_trigger_generation: Optional[bool]) -> None:
        json_obj = {"text": text, "try_trigger_generation": try_trigger_generation}
        json_str = Utils.json_dumps(json_obj)

        await self.websocket.send(json_str)

    async def _init(self) -> None:
        await self.asend(text=" ", try_trigger_generation=False)

    async def anext_audio(self) -> Optional[Audio]:
        json_str = await self.websocket.recv()
        audio_output = AudioOutput.model_validate_json(json_str)

        if audio_output.audio is None:
            return None

        return Audio.new(byte_str=audio_output.byte_str(), audio_format=self.AUDIO_FORMAT, audio_info=self.AUDIO_INFO)

    def tts(self) -> ElevenLabs:
        return ElevenLabs.new(eleven_labs_websocket=self)
