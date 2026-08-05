"""Conversation messages and turns.

This module closes the FIXME at ``bfcl_eval/utils.py`` ("use a data class to abstract
the audio message and image message for clearer readability").

The on-disk shape of ``question`` is always ``list[turn][message]`` -- a list of
turns, each a list of message objects -- for every test category, including the
single-turn ones (which have exactly one turn).  ``Conversation`` wraps that and
gives every mutation the pipeline performs a name.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterator

from bfcl_eval.schemas.serde import dump_extras, split_known


class Role(str, Enum):
    """Message role.

    The ``str`` mixin is deliberate: ``msg.role == "user"`` keeps working while call
    sites migrate off raw dicts, and ``json.dumps`` handles it without a custom
    encoder.
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class ImageContent:
    """One image attached to a user message.

    Injected at load time by the vision loader, not present on disk.  Both the raw
    bytes and the base64 encoding are stored rather than derived: the loader writes
    them as independent keys and round-trip fidelity is worth more here than saving
    a few hundred kilobytes.

    Frozen so ``__deepcopy__`` can return ``self``.  Vision entries carry 200KB-1MB
    JPEG payloads and are deep-copied once per model plus once per logged step.
    """

    image_path: str
    mime_type: str = "image/jpeg"  # wire key is "type"
    image_base64: str = field(default="", repr=False, compare=False)
    image_bytes: bytes = field(default=b"", repr=False, compare=False)

    _WIRE_KEYS = frozenset({"image_path", "type", "image_base64", "image_bytes"})

    def __deepcopy__(self, memo) -> "ImageContent":
        # Sound only because this class is frozen.
        return self

    @classmethod
    def from_dict(cls, raw: dict) -> "ImageContent":
        known, annotations, extras = split_known(raw, cls._WIRE_KEYS)
        # Images carry no annotations/extras today; fold any into the base64 payload's
        # sibling keys would corrupt the round trip, so assert loudly instead.
        if annotations or extras:
            raise ValueError(f"unexpected keys on image content: {sorted(annotations | extras)}")
        return cls(
            image_path=known["image_path"],
            mime_type=known.get("type", "image/jpeg"),
            image_base64=known.get("image_base64", ""),
            image_bytes=known.get("image_bytes", b""),
        )

    @classmethod
    def from_bytes(cls, image_path: str, data: bytes, mime_type: str = "image/jpeg") -> "ImageContent":
        return cls(
            image_path=image_path,
            mime_type=mime_type,
            image_base64=base64.b64encode(data).decode("utf-8"),
            image_bytes=data,
        )

    def to_dict(self, *, redact_binary: bool = False) -> dict:
        """Serialize.

        ``redact_binary`` drops the heavy payloads, for inference logs.  This
        replaces the ``deepcopy`` + ``del image_content["image_bytes"]`` dance in
        ``base_handler``.
        """
        out: dict[str, Any] = {}
        if not redact_binary:
            out["image_base64"] = self.image_base64
            out["image_bytes"] = self.image_bytes
        out["image_path"] = self.image_path
        out["type"] = self.mime_type
        return out


@dataclass(frozen=True, slots=True)
class AudioContent:
    """Native audio payload for the ``true_audio`` modality.

    Replaces the bare ``bytes`` currently stored under ``msg["audio_content"]``.
    """

    audio_bytes: bytes = field(default=b"", repr=False, compare=False)
    audio_path: str | None = None
    audio_format: str = "mp3"

    def __deepcopy__(self, memo) -> "AudioContent":
        return self

    def base64(self) -> str:
        return base64.b64encode(self.audio_bytes).decode("utf-8")


@dataclass(frozen=True, slots=True)
class AudioSource:
    """On-disk audio provenance for a message.

    The audio datasets ship a sidecar of transcription and noise metadata alongside
    each user message.  The loader currently deletes these keys outright; modeling
    them means the choice of which text to use ("clean deepgram ASR" vs "the human
    transcript") becomes a one-line policy instead of three commented-out lines.

    ``asr`` is keyed by the suffix after ``asr_`` -- e.g. ``"deepgram_audio_clean"``
    for the wire key ``asr_deepgram_audio_clean``.  The real corpus uses
    ``asr_{engine}_audio_{clean,noisy}``.
    """

    transcript: str | None = None
    speech_like_features: Any = None
    audio_path: str | None = None
    audio_path_noisy: str | None = None
    base_content: str | None = None
    noise_effects_applied: Any = None
    noise_processing_success: Any = None
    asr: dict[str, str] = field(default_factory=dict)

    ASR_PREFIX = "asr_"

    # Non-ASR wire keys owned by this sidecar.
    WIRE_KEYS = frozenset(
        {
            "transcript",
            "speech_like_features",
            "audio_path",
            "audio_path_noisy",
            "base_content",
            "noise_effects_applied",
            "noise_processing_success",
        }
    )

    @classmethod
    def owns(cls, key: str) -> bool:
        return key in cls.WIRE_KEYS or key.startswith(cls.ASR_PREFIX)

    @classmethod
    def from_dict(cls, raw: dict) -> "AudioSource":
        asr = {
            key[len(cls.ASR_PREFIX) :]: value
            for key, value in raw.items()
            if key.startswith(cls.ASR_PREFIX)
        }
        return cls(
            transcript=raw.get("transcript"),
            speech_like_features=raw.get("speech_like_features"),
            audio_path=raw.get("audio_path"),
            audio_path_noisy=raw.get("audio_path_noisy"),
            base_content=raw.get("base_content"),
            noise_effects_applied=raw.get("noise_effects_applied"),
            noise_processing_success=raw.get("noise_processing_success"),
            asr=asr,
        )

    def to_dict(self) -> dict:
        out: dict[str, Any] = {}
        for name in (
            "transcript",
            "speech_like_features",
            "audio_path",
            "base_content",
            "audio_path_noisy",
            "noise_effects_applied",
            "noise_processing_success",
        ):
            value = getattr(self, name)
            if value is not None:
                out[name] = value
        for suffix, text in self.asr.items():
            out[f"{self.ASR_PREFIX}{suffix}"] = text
        return out

    def text(self, engine_key: str) -> str:
        """Return one ASR transcription, e.g. ``text("deepgram_audio_clean")``."""
        return self.asr[engine_key]


@dataclass(slots=True)
class Message:
    """One message in one conversation turn.

    Mutable: handlers rewrite ``role`` and append to ``content`` in place.
    """

    role: Role
    content: str | None = None
    images: list[ImageContent] = field(default_factory=list)
    audio: AudioContent | None = None
    audio_source: AudioSource | None = None
    # Pre-ASR text, kept for debugging on the ``text_audio`` modality.
    original_content: str | None = None
    clarifications: Any = None
    extras: dict[str, Any] = field(default_factory=dict, repr=False)
    annotations: dict[str, Any] = field(default_factory=dict, repr=False)

    _WIRE_KEYS = frozenset(
        {
            "role",
            "content",
            "image_content",
            "audio_content",
            # The container the bytes are in. The corpus is mp3 throughout, which is
            # why ``AudioContent`` defaults to it -- but the key is modeled so the
            # loader can say otherwise. It could not before: the key fell through to
            # ``extras`` behind a warning, and every provider was told "mp3" whatever
            # the bytes actually were.
            "audio_format",
            "original_content",
            "clarifications",
        }
    )

    @property
    def has_image(self) -> bool:
        return bool(self.images)

    @property
    def has_audio(self) -> bool:
        return self.audio is not None

    @classmethod
    def from_dict(cls, raw: dict) -> "Message":
        audio_keys = {k: v for k, v in raw.items() if AudioSource.owns(k)}
        rest = {k: v for k, v in raw.items() if k not in audio_keys}
        known, annotations, extras = split_known(rest, cls._WIRE_KEYS)

        images = [ImageContent.from_dict(i) for i in known.get("image_content") or []]

        raw_audio = known.get("audio_content")
        if raw_audio is None:
            audio = None
        elif isinstance(raw_audio, AudioContent):
            audio = raw_audio
        else:
            audio = AudioContent(
                audio_bytes=raw_audio,
                audio_path=audio_keys.get("audio_path"),
                audio_format=known.get("audio_format", "mp3"),
            )

        return cls(
            role=Role(known["role"]),
            content=known.get("content"),
            images=images,
            audio=audio,
            audio_source=AudioSource.from_dict(audio_keys) if audio_keys else None,
            original_content=known.get("original_content"),
            clarifications=known.get("clarifications"),
            extras=extras,
            annotations=annotations,
        )

    def to_dict(self, *, redact_binary: bool = False) -> dict:
        out: dict[str, Any] = {"role": self.role.value}
        if self.content is not None:
            out["content"] = self.content
        if self.audio_source is not None:
            out.update(self.audio_source.to_dict())
        if self.images:
            out["image_content"] = [i.to_dict(redact_binary=redact_binary) for i in self.images]
        if self.audio is not None:
            # The redacted form is a *string*, not `b""`: this goes straight into a
            # result file, and an empty bytes object is not JSON-serializable -- it
            # used to reach `make_json_serializable`, whose bare except turned it into
            # the literal text "b''". Saying how much was elided is more useful anyway.
            out["audio_content"] = (
                f"<{len(self.audio.audio_bytes)} bytes of "
                f"{self.audio.audio_format} elided>"
                if redact_binary
                else self.audio.audio_bytes
            )
            if self.audio.audio_format != "mp3":
                out["audio_format"] = self.audio.audio_format
        if self.original_content is not None:
            out["original_content"] = self.original_content
        if self.clarifications is not None:
            out["clarifications"] = self.clarifications
        return dump_extras(out, self.annotations, self.extras)


# One turn is a flat list of messages.
Turn = list[Message]


@dataclass(slots=True)
class Conversation:
    """``question`` as a first-class object: a list of turns, each a list of messages.

    Every mutation the pipeline performs on a conversation has a named method here.
    That is the point -- ``entry.conversation.prepend_system_message(...)`` is
    greppable in a way that ``entry["question"][0].insert(0, {...})`` is not.
    """

    turns: list[Turn] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.turns)

    def __iter__(self) -> Iterator[Turn]:
        return iter(self.turns)

    def __getitem__(self, index: int) -> Turn:
        return self.turns[index]

    def __setitem__(self, index: int, value: Turn) -> None:
        self.turns[index] = value

    @property
    def first_turn(self) -> Turn:
        return self.turns[0]

    def iter_messages(self) -> Iterator[tuple[int, int, Message]]:
        for turn_index, turn in enumerate(self.turns):
            for message_index, message in enumerate(turn):
                yield turn_index, message_index, message

    def empty_turn_indices(self) -> list[int]:
        """Turns with no messages -- the holdout positions in ``multi_turn_miss_func``."""
        return [i for i, turn in enumerate(self.turns) if not turn]

    # ---- named mutations -------------------------------------------------

    def map_turns(self, fn: Callable[[Turn], Turn]) -> None:
        """Rewrite every turn in place.

        Replaces the per-round rewrite loop hand-rolled in five API handlers.
        """
        self.turns = [fn(turn) for turn in self.turns]

    def prepend_system_message(self, content: str) -> None:
        """Insert a system message at the very front of the first turn."""
        self.turns[0].insert(0, Message(role=Role.SYSTEM, content=content))

    def pop_system_prompt(self) -> str | None:
        """Remove and return the first system message, if any.

        Destructive by design -- it mirrors ``extract_system_prompt``, which the
        provider handlers rely on to strip the system turn before sending.
        """
        for turn in self.turns:
            for index, message in enumerate(turn):
                if message.role is Role.SYSTEM:
                    del turn[index]
                    return message.content
        return None

    def drain_system_prompts(self) -> list[str]:
        """Remove every system message and return their contents in document order."""
        collected: list[str] = []
        for turn in self.turns:
            for index in reversed(range(len(turn))):
                if turn[index].role is Role.SYSTEM:
                    collected.append(turn.pop(index).content or "")
        collected.reverse()
        return collected

    # ---- serialization ---------------------------------------------------

    @classmethod
    def from_list(cls, raw: list[list[dict]]) -> "Conversation":
        return cls(turns=[[Message.from_dict(m) for m in turn] for turn in raw])

    def to_list(self, *, redact_binary: bool = False) -> list[list[dict]]:
        return [[m.to_dict(redact_binary=redact_binary) for m in turn] for turn in self.turns]
