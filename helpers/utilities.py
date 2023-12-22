import os
import logging

import disnake
import autocorrect
import pytesseract

pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
logger = logging.getLogger("sauron-bot")

def twos_complement(hexstr: str, bits: int):
    value = int(hexstr, 16) # convert hexadecimal to integer

    # convert from unsigned number to signed number with "bits" bits
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value

def text_post_processing(text: str) -> str:
    # Remove non-ASCII characters
    logger.debug(f"Original text: {text}")
    text = "".join([c if ord(c) < 128 else "" for c in text]).strip()
    logger.debug(f"ASCII text: {text}")
    
    # Correct spelling
    spell = autocorrect.Speller(only_replacements=True) # https://github.com/filyp/autocorrect#ocr
    logger.debug(f"Pre-corrected text: {spell(text)}")
    text = spell(text)
    logger.debug(f"Corrected text: {text}")
    
    return text

def validate_attachment(attachment: disnake.Attachment) -> bool:
    if attachment.content_type is None:
        if not attachment.filename.lower().endswith((".png", ".PNG", ".jpg", ".jpeg", ".JPG", ".JPEG", ".mp4", ".webm")):
            return False
    elif not attachment.content_type.startswith(("image", "video")):
        return False
    if not attachment.filename.lower().endswith((".png", ".PNG", ".jpg", ".jpeg", ".JPG", ".JPEG", ".mp4", ".webm")):
        return False
    return True
