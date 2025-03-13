import pytesseract
import imagehash
from gradio_client import handle_file
from PIL import Image

import utils


class ImageProcessor:
    def __init__(self, filename: str) -> None:
        self.path = filename
        self.image = Image.open(filename)
        self.hash = utils.twos_complement(str(imagehash.phash(self.image)), 64)

    def __del__(self) -> None:
        pass

    def ocr(self, prefer_florence_2: bool = False) -> str:
        if prefer_florence_2:
            try:
                result = self.florence_client.predict(
                    image=handle_file(self.path),
                    task_prompt="OCR",
                    text_input=None,
                    model_id="microsoft/Florence-2-large",
                    api_name="/process_image",
                )

                # Strip {'<OCR>': ' from the front and '} from the back
                text = result[0][11:-2]
            except Exception as e:
                logger.warning(f"Couldn't use Florence-2 for OCR. Reason: {e}")
                text = pytesseract.image_to_string(self.image)
        else:
            text = pytesseract.image_to_string(self.image)
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
