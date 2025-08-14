import asyncio
import contextlib
import dataclasses
from asyncio import AbstractEventLoop
from collections.abc import Iterator
from typing import ClassVar, Self

import _cffi_backend  # ty: ignore[unresolved-import]
from _cffi_backend import _CDataBase as CDataBase  # pylint: disable=no-name-in-module  # ty: ignore[unresolved-import]
from sounddevice import CallbackFlags, RawInputStream

from mkutils.audio import Audio, AudioFormat, AudioInfo
from mkutils.enum import Enum
from mkutils.logger import Logger
from mkutils.queue import Queue
from mkutils.utils import Utils

logger: Logger = Logger.new(__name__)


@Utils.keyed_by(attr="key")
@dataclasses.dataclass(frozen=True, kw_only=True)
class DtypeInfo:
    key: str
    audio_format: AudioFormat


class Dtype(Enum):
    INT_16 = DtypeInfo(key="int16", audio_format=AudioFormat.PCM_S16LE)
    FLOAT_32 = DtypeInfo(key="float32", audio_format=AudioFormat.FLOAT)


# NOTE: inspired by: [https://python-sounddevice.readthedocs.io/en/0.5.1/examples.html#creating-an-asyncio-generator-for-audio-blocks]  # pylint: disable=line-too-long  # noqa: E501
@dataclasses.dataclass(frozen=True, kw_only=True)
class Microphone:
    DEFAULT_DEVICE: ClassVar[int] = 0
    DEFAULT_DTYPE: ClassVar[Dtype] = Dtype.FLOAT_32
    ZERO_INPUT_CHANNELS_ERROR_MESSAGE: ClassVar[str] = "selected device does not have any input channels"

    audio_info: AudioInfo
    dtype: Dtype
    audio_queue: Queue[Audio]
    event_loop: AbstractEventLoop

    @classmethod
    def new(cls, *, device: int = DEFAULT_DEVICE, dtype: Dtype = DEFAULT_DTYPE) -> Self:
        audio_info = AudioInfo.from_device(device=device)
        microphone = cls(
            audio_info=audio_info, dtype=dtype, audio_queue=Queue.new(), event_loop=asyncio.get_running_loop()
        )

        if audio_info.num_channels == 0:
            raise ValueError(cls.ZERO_INPUT_CHANNELS_ERROR_MESSAGE)

        return microphone

    @contextlib.contextmanager
    def context(self) -> Iterator[None]:
        with self._raw_input_stream():
            yield None

    # NOTE: type annotations gotten from logging
    def _callback(
        self,
        indata: _cffi_backend.buffer,  # pylint: disable=c-extension-no-member
        _frame_count: int,
        _time_info: CDataBase,
        _status: CallbackFlags,
    ) -> None:
        # NOTE: _cffi_backend.buffer returns bytes when sliced
        audio = Audio.new(byte_str=indata[:], audio_format=self.dtype.value.audio_format, audio_info=self.audio_info)

        # NOTE: do this rather than [self.audio_queue.get_event_loop().create_task(asend_coro)] to preclude the
        # possibility of microphone inputs getting added out of order
        self.event_loop.call_soon_threadsafe(self.audio_queue.append, audio)

    def _raw_input_stream(self) -> RawInputStream:
        return RawInputStream(
            samplerate=self.audio_info.sample_rate,
            channels=self.audio_info.num_channels,
            dtype=self.dtype.value.key,
            callback=self._callback,
        )
