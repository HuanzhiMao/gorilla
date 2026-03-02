"""
Shared utilities for executable backend functions.
"""

import base64


class ImageResult:
    """
    Return type for functions that produce image output.
    
    Usage:
        from bfcl_eval.eval_checker.multi_turn_eval.func_source_code import ImageResult
        
        def fetch_image(self, url: str) -> ImageResult:
            # ... fetch image ...
            return ImageResult(base64_data, "image/jpeg")
    """
    
    def __init__(self, image_base64: str="", image_bytes: bytes=b"", mime_type: str = "image/jpeg"):
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
        
        self.type = mime_type
    
    def to_dict(self) -> dict:
        return {
            "image_base64": self.image_base64,
            "image_bytes": self.image_bytes,
            "type": self.type,
        }
