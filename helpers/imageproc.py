import os
import logging

import aiohttp
import aiofiles
import pytesseract
import imagehash
from PIL import Image

logger = logging.getLogger("sauron-bot")

class ImageProc:
    def __init__(self, session: aiohttp.ClientSession, cache_dir: str) -> None:
        self.session = session
        self.cache_dir = cache_dir
        pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

    async def download_image(self, url: str) -> str | None:
        try:
            image_filename = os.path.basename(url).split("?")[0]
            image_path = os.path.join(self.cache_dir, image_filename)

            if not os.path.exists(image_path):
                async with self.session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Downloading image {url} returned status code `{response.status}`")
                        return None
                    async with aiofiles.open(image_path, mode="wb") as f:
                        await f.write(await response.read())
                    logger.info(f"Downloaded image {image_path}")
            return image_path
        except Exception as err:
            logger.error(f"Downloading image returned invalid data! {err}")
            return None
    
    def twos_complement(self, hexstr, bits):
        value = int(hexstr, 16) # convert hexadecimal to integer

		# convert from unsigned number to signed number with "bits" bits
        if value & (1 << (bits - 1)):
            value -= 1 << bits
        return value

    def ocr_core(self, filename: str) -> str:
        text = pytesseract.image_to_string(Image.open(filename))
        return text

    def create_image_hash(self, filename: str) -> int:
        img_hash = str(imagehash.phash(Image.open(filename)))
        hash_int = self.twos_complement(img_hash, 64) # convert from hexadecimal to 64 bit signed integer
        return hash_int

    def check_image_hash_similarity(self, hash1: imagehash.ImageHash, hash2: imagehash.ImageHash, threshold: int = 10):
        hamming_distance = hash1 - hash2
        similar = hamming_distance <= threshold
        return similar
