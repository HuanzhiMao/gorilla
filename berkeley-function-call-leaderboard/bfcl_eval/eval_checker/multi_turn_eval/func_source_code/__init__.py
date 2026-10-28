"""
Shared utilities for executable backend functions.
"""

import base64
import hashlib
from typing import Any


class ImageResult:
    """
    Return type for functions that produce image output.

    Usage:
        from bfcl_eval.eval_checker.multi_turn_eval.func_source_code import ImageResult

        def fetch_image(self, url: str) -> ImageResult:
            # ... fetch image ...
            return ImageResult(base64_data, mime_type="image/jpeg")

    The object itself -- not a plain dict -- is what ``execute_multi_turn_func_call``
    puts in an execution result's ``"result"`` slot. Handlers reach for the payload
    attributes; anything bound for disk calls ``to_dict(redact_binary=True)``. This
    mirrors :class:`~bfcl_eval.schemas.message.ImageContent`, which does the same for
    the image *input* side.
    """

    def __init__(
        self,
        image_base64: str = "",
        image_bytes: bytes = b"",
        mime_type: str = "image/jpeg",
    ):
        if image_base64 and image_bytes:
            self.image_base64 = image_base64
            self.image_bytes = image_bytes
        elif image_base64:
            self.image_base64 = image_base64
            self.image_bytes = base64.b64decode(image_base64)
        elif image_bytes:
            self.image_bytes = image_bytes
            self.image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        else:
            raise ValueError("Either image_base64 or image_bytes must be provided")

        self.mime_type = mime_type

    @property
    def size_bytes(self) -> int:
        """Size of the decoded image."""
        return len(self.image_bytes)

    @property
    def digest(self) -> str:
        """Short content hash -- enough to tell two logged images apart."""
        return hashlib.sha256(self.image_bytes).hexdigest()[:12]

    def to_dict(self, *, redact_binary: bool = False) -> dict[str, Any]:
        """Serialize.

        ``redact_binary`` drops the payload and leaves the shape behind, for score and
        result files. A geoguessr turn returns a panorama per step, so the unredacted
        form is ~1MB of base64 plus the same image again as bytes -- none of it
        readable once written. Following ``Message.to_dict``, the redacted form says
        how much was elided rather than pretending the image was empty, and carries a
        digest so a reader can still tell whether two steps returned the same image.
        """
        if redact_binary:
            return {
                "type": self.mime_type,
                "image_elided": f"<{self.size_bytes} bytes of {self.mime_type} elided>",
                "sha256": self.digest,
            }
        return {
            "image_base64": self.image_base64,
            "image_bytes": self.image_bytes,
            "type": self.mime_type,
        }

    def __repr__(self) -> str:
        # Deliberately payload-free, and the reason this class is safe to hold in a
        # structure that might be logged: `make_json_serializable` cannot encode an
        # `ImageResult` and falls back to `str()`, so this repr is the backstop that
        # keeps base64 off disk even on a path that forgot to redact.
        return (
            f"<ImageResult {self.mime_type} {self.size_bytes} bytes "
            f"sha256:{self.digest}>"
        )

    def __eq__(self, other: object) -> bool:
        # `response_checker` matches model execution results against ground truth ones
        # with `list.remove`, i.e. by `==`. Default identity semantics would fail every
        # image comparison, including an image compared against itself across the two
        # separately-executed instance sets.
        if not isinstance(other, ImageResult):
            return NotImplemented
        return (
            self.image_bytes == other.image_bytes and self.mime_type == other.mime_type
        )

    def __hash__(self) -> int:
        return hash((self.image_bytes, self.mime_type))
