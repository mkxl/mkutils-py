import asyncio
import dataclasses
from collections.abc import Iterable
from io import BytesIO
from typing import Annotated, ClassVar, Optional, Self

import numpy
import sounddevice
import soundfile
import torch
import torchaudio
from pydub import AudioSegment

from mkutils.enum import Enum
from mkutils.time import Duration
from mkutils.typing import JsonObject
from mkutils.utils import Shape, Utils


@Utils.keyed_by(attr="key")
@dataclasses.dataclass(frozen=True, kw_only=True)
class AudioFormatInfo:
    key: str
    format: str
    subtype: Optional[str]
    pcm_sample_width: Optional[int]

    def pair(self) -> tuple[str, Optional[str]]:
        return (self.format, self.subtype)


class AudioFormat(Enum):
    PCM_FLOAT_32 = AudioFormatInfo(key="pcm_float_32", format="RAW", subtype="FLOAT", pcm_sample_width=4)
    PCM_FLOAT_64 = AudioFormatInfo(key="pcm_float_64", format="RAW", subtype="DOUBLE", pcm_sample_width=8)
    PCM_S16LE = AudioFormatInfo(key="pcm_s16le", format="RAW", subtype="PCM_16", pcm_sample_width=2)
    WAV = AudioFormatInfo(key="wav", format="WAV", subtype=None, pcm_sample_width=None)
    MP3 = AudioFormatInfo(key="mp3", format="MP3", subtype=None, pcm_sample_width=None)


@dataclasses.dataclass(frozen=True, kw_only=True)
class AudioInfo:
    sample_rate: int
    num_channels: int

    @classmethod
    def from_device(cls, device: int) -> Self:
        # NOTE: [https://python-sounddevice.readthedocs.io/en/0.5.1/api/checking-hardware.html#sounddevice.query_devices]  # pylint: disable=line-too-long  # noqa: E501
        sound_device = sounddevice.query_devices(device=device)
        sample_rate = int(sound_device["default_samplerate"])
        num_channels = sound_device["max_input_channels"]
        audio_info = cls(sample_rate=sample_rate, num_channels=num_channels)

        return audio_info

    def pair(self) -> tuple[int, int]:
        return (self.sample_rate, self.num_channels)


@dataclasses.dataclass(kw_only=True)
class Audio:
    ALWAYS_2D: ClassVar[bool] = True
    AXIS_CHANNELS: ClassVar[int] = 1
    AXIS_FRAMES: ClassVar[int] = 0
    BLOCK_ON_PLAY: ClassVar[bool] = True

    data: Annotated[numpy.ndarray, Shape("F,C")]
    sample_rate: int

    # NOTE: implemented to avoid having to do [type(self)(data=data, sample_rate=sample_rate)]
    @classmethod
    def from_values(cls, *, data: Annotated[numpy.ndarray, Shape("F,C")], sample_rate: int) -> Self:
        return cls(data=data, sample_rate=sample_rate)

    @classmethod
    def silence(cls, *, num_samples: int, num_channels: int, sample_rate: int) -> Self:
        data = numpy.zeros((num_samples, num_channels))
        audio = cls.from_values(data=data, sample_rate=sample_rate)

        return audio

    # pylint: disable=redefined-builtin
    @classmethod
    def new(
        cls, *, byte_str: bytes, audio_format: Optional[AudioFormat] = None, audio_info: Optional[AudioInfo] = None
    ) -> Self:
        file = BytesIO(byte_str)
        format, subtype = (None, None) if audio_format is None else audio_format.value.pair()
        samplerate, channels = (None, None) if audio_info is None else audio_info.pair()
        data, sample_rate = soundfile.read(
            file,
            always_2d=cls.ALWAYS_2D,
            samplerate=samplerate,
            channels=channels,
            format=format,
            subtype=subtype,
        )
        audio = cls.from_values(data=data, sample_rate=sample_rate)

        return audio

    # NOTE-37cb5e: assumes all the audio instances share the same sample rate
    @classmethod
    def cat(cls, audio_iter: Iterable[Self]) -> Self:
        audio_iter = iter(audio_iter)
        first_audio = next(audio_iter)
        data_list = [first_audio.data]

        for audio in audio_iter:
            data_list.append(audio.data)

        data = numpy.vstack(data_list)
        audio = cls.from_values(data=data, sample_rate=first_audio.sample_rate)

        return audio

    def is_empty(self) -> bool:
        return self.num_frames() == 0

    def is_nonempty(self) -> bool:
        return not self.is_empty()

    # NOTE-37cb5e
    def add(self, other: Self) -> None:
        data_list = [self.data, other.data]
        self.data = numpy.vstack(data_list)

    def with_data(self, data: Annotated[numpy.ndarray, Shape("F,C")]) -> None:
        return self.from_values(data=data, sample_rate=self.sample_rate)

    def slice(self, *, begin: int, end: int) -> Self:
        data = self.data[begin:end, :]
        audio = self.with_data(data)

        return audio

    def resample(self, *, sample_rate: int) -> Self:
        if self.sample_rate == sample_rate:
            return self

        waveform = torch.from_numpy(self.data.T)
        data_torch = torchaudio.functional.resample(waveform=waveform, orig_freq=self.sample_rate, new_freq=sample_rate)
        audio = self.from_values(data=data_torch.T.numpy(), sample_rate=sample_rate)

        return audio

    def mean(self, *, num_channels: int) -> Self:
        data = self.data.mean(axis=self.AXIS_CHANNELS, keepdims=True)
        data = numpy.tile(data, (1, num_channels))
        audio = self.with_data(data)

        return audio

    def split(self, *, num_frames: int) -> tuple[Self, Self]:
        data_1 = self.data[:num_frames, :]
        data_2 = self.data[num_frames:, :]
        audio_1 = self.from_values(data=data_1, sample_rate=self.sample_rate)
        audio_2 = self.from_values(data=data_2, sample_rate=self.sample_rate)

        return (audio_1, audio_2)

    def describe(self) -> JsonObject:
        return {
            "sample_rate": self.sample_rate,
            "shape": tuple(self.data.shape),
        }

    def num_frames(self) -> int:
        return self.data.shape[self.AXIS_FRAMES]

    def num_channels(self) -> int:
        return self.data.shape[self.AXIS_CHANNELS]

    def info(self) -> AudioInfo:
        return AudioInfo(sample_rate=self.sample_rate, num_channels=self.num_channels())

    def byte_str(self, *, audio_format: AudioFormat) -> bytes:
        bytes_io = BytesIO()
        soundfile.write(
            bytes_io,
            self.data,
            samplerate=self.sample_rate,
            subtype=audio_format.value.subtype,
            format=audio_format.value.format,
        )

        return bytes_io.getvalue()

    def segment(self) -> AudioSegment:
        data = self.byte_str(audio_format=AudioFormat.PCM_S16LE)
        audio_segment = AudioSegment(
            data=data,
            sample_width=AudioFormat.PCM_S16LE.value.pcm_sample_width,
            frame_rate=self.sample_rate,
            channels=self.num_channels(),
        )

        return audio_segment

    async def aplay(self) -> None:
        await asyncio.to_thread(
            sounddevice.play, data=self.data, samplerate=self.sample_rate, blocking=self.BLOCK_ON_PLAY
        )

    def duration(self) -> Duration:
        seconds = self.num_frames() / self.sample_rate
        duration = Duration.new(seconds=seconds)

        return duration
