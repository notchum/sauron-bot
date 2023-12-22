import logging

import pytesseract
import imagehash
from PIL import Image

from helpers.utilities import twos_complement, text_post_processing

logger = logging.getLogger("sauron-bot")

class ImageProcessor:
    def __init__(self, filename: str) -> None:
        self.path = filename
        self.image = Image.open(filename)
        self.hash = twos_complement(str(imagehash.phash(self.image)), 64)
    
    def __del__(self) -> None:
        pass

    def ocr(self) -> str:
        text = pytesseract.image_to_string(self.image)
        text = text_post_processing(text)
        return text
        
    def check_hash_similarity(self, hash1: imagehash.ImageHash, hash2: imagehash.ImageHash, threshold: int = 10):
        hamming_distance = hash1 - hash2
        similar = hamming_distance <= threshold
        return similar
