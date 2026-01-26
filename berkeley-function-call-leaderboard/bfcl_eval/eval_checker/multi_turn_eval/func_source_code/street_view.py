import base64

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code import ImageResult


class StreetViewAPI:
    def __init__(self):
        self._api_description = "This tool belongs to the Vision Test API category. It provides functions to test the vision of the model."

    def fetch_image(self) -> ImageResult:
        """
        This function tests the vision of the model.
        """
        def encode_image(image_path):
            with open(image_path, "rb") as image_file:
                return image_file.read()
        
        image_bytes = encode_image("/Users/hans/Desktop/images.jpeg")
        return ImageResult(image_bytes, "image/jpeg")