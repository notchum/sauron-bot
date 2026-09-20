import imagehash
from gradio_client import Client, handle_file
from PIL import Image

import utils


class ImageProcessor:
    def __init__(self, filename: str, ocr_client: Client) -> None:
        self.path = filename
        self.ocr_client = ocr_client
        self.image = Image.open(filename)
        self.hash = utils.twos_complement(str(imagehash.phash(self.image)), 64)

    def __del__(self) -> None:
        pass

    def ocr(self) -> str:
        text = self.ocr_client.predict(
            filepath=handle_file(self.path),
            languages=["eng"],
            api_name="/tesseract-ocr",
        )
        # text = utils.text_post_processing(text)
        return text

    def check_hash_similarity(
        self,
        hash1: imagehash.ImageHash,
        hash2: imagehash.ImageHash,
        threshold: int = 10,
    ):
        hamming_distance = hash1 - hash2
        similar = hamming_distance <= threshold
        return similar
