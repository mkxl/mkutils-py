import abc
import dataclasses
import wave
from io import BytesIO
from typing import ClassVar, Protocol, Self

from lameenc import Encoder as LameEncoder  # ty: ignore[unresolved-import]  pylint: disable=no-name-in-module

from mkutils.audio import Audio, AudioFormat, AudioInfo
from mkutils.buffer import ByteBuffer
from mkutils.time import Duration


class AudioEncoder(Protocol):
    @abc.abstractmethod
    def push(self, *, audio: Audio, finish: bool) -> bytes:
        raise NotImplementedError


@dataclasses.dataclass(frozen=True, kw_only=True)
class PcmAudioEncoder(AudioEncoder):
    pcm_audio_format: AudioFormat

    @classmethod
    def new(cls, *, pcm_audio_format: AudioFormat) -> Self:
        return cls(pcm_audio_format=pcm_audio_format)

    def push(self, *, audio: Audio, finish: bool) -> bytes:
        return audio.byte_str(audio_format=self.pcm_audio_format)


@dataclasses.dataclass(kw_only=True)
class WavAudioEncoder(AudioEncoder):
    INITIAL_YIELDED_HEADER: ClassVar[bool] = False

    pcm_audio_format: AudioFormat
    header_duration: Duration
    yielded_header: bool

    @classmethod
    def new(cls, *, pcm_audio_format: AudioFormat, header_duration: Duration) -> Self:
        return cls(
            pcm_audio_format=pcm_audio_format,
            header_duration=header_duration,
            yielded_header=cls.INITIAL_YIELDED_HEADER,
        )

    def _wav_byte_buffer(self, *, audio_info: AudioInfo) -> ByteBuffer:
        bytes_io = BytesIO()
        num_frames = self.header_duration.sample_index(sample_rate=audio_info.sample_rate)

        # NOTE: [https://docs.python.org/3/library/wave.html#wave.Wave_write], wave_write.writeframes() and
        # wave_write.close() will correct the number of frames in the header
        with wave.open(bytes_io, "wb") as wave_write:
            wave_write.setnframes(num_frames)  # pylint: disable=no-member
            wave_write.setnchannels(audio_info.num_channels)  # pylint: disable=no-member
            wave_write.setsampwidth(self.pcm_audio_format.value.pcm_sample_width)  # pylint: disable=no-member
            wave_write.setframerate(audio_info.sample_rate)  # pylint: disable=no-member
            wave_write.writeframesraw(b"")  # pylint: disable=no-member

            return ByteBuffer.new(byte_str=bytes_io.getvalue())

    def push(self, *, audio: Audio, finish: bool) -> bytes:
        pcm_byte_str = audio.byte_str(audio_format=self.pcm_audio_format)

        if self.yielded_header:
            return pcm_byte_str

        wav_byte_buffer = self._wav_byte_buffer(audio_info=audio.info())
        self.yielded_header = True

        wav_byte_buffer.push(pcm_byte_str)

        return wav_byte_buffer.value()


@dataclasses.dataclass(kw_only=True)
class Mp3AudioEncoder(AudioEncoder):
    BIT_RATE: ClassVar[int] = 128
    QUALITY: ClassVar[int] = 2
    INITIAL_LAME_ENCODER_IS_CONFIGURED: ClassVar[bool] = False
    INITIAL_IS_EMPTY: ClassVar[bool] = True

    pcm_audio_format: AudioFormat
    lame_encoder: LameEncoder
    lame_encoder_is_configured: bool
    is_empty: bool

    @classmethod
    def new(cls, *, pcm_audio_format: AudioFormat) -> Self:
        return cls(
            pcm_audio_format=pcm_audio_format,
            lame_encoder=cls._lame_encoder(),
            lame_encoder_is_configured=cls.INITIAL_LAME_ENCODER_IS_CONFIGURED,
            is_empty=cls.INITIAL_IS_EMPTY,
        )

    @classmethod
    def _lame_encoder(cls) -> LameEncoder:
        lame_encoder = LameEncoder()

        lame_encoder.set_bit_rate(cls.BIT_RATE)
        lame_encoder.set_quality(cls.QUALITY)

        return lame_encoder

    def _configure_lame_encoder(self, *, audio_info: AudioInfo) -> None:
        self.lame_encoder.set_in_sample_rate(audio_info.sample_rate)
        self.lame_encoder.set_channels(audio_info.num_channels)

        self.lame_encoder_is_configured = True

    def _push(self, *, audio: Audio) -> bytes:
        pcm_byte_str = audio.byte_str(audio_format=self.pcm_audio_format)
        mp3_byte_str = self.lame_encoder.encode(pcm_byte_str)
        self.is_empty &= audio.is_empty()

        return mp3_byte_str

    def push(self, *, audio: Audio, finish: bool) -> bytes:
        if not self.lame_encoder_is_configured:
            self._configure_lame_encoder(audio_info=audio.info())

        mp3_byte_str = self._push(audio=audio)

        if not finish:
            return mp3_byte_str

        mp3_byte_buffer = ByteBuffer.new(byte_str=mp3_byte_str)

        # NOTE: self.lame_encoder.flush() raises an exception if called before self.lame_encoder.encode() is
        if self.is_empty:
            silent_audio = Audio.silence(
                num_samples=1, num_channels=audio.num_channels(), sample_rate=audio.sample_rate
            )
            silent_mp3_byte_str = self._push(audio=silent_audio)

            mp3_byte_buffer.push(silent_mp3_byte_str)

        mp3_byte_buffer.push(self.lame_encoder.flush())

        return mp3_byte_buffer.value()
