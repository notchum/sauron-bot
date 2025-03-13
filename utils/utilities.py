import os
from typing import List

import disnake
import autocorrect
import pytesseract
from loguru import logger

pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

##*************************************************##
##********          DISCORD UTILS           *******##
##*************************************************##


def slash_command_mention(name: str, id: int) -> str:
    """A helper function to format a slash command as a Discord clickable mention.

    Parameters
    ----------
    name: :class:`str`
        The name of the command to mention.
    id: :class:`int`
        The ID of the command to mention.
        Obtained by typing the slash command in Discord and right-clicking on the
        pop-up box then 'Copy Command ID'.

    Returns
    -------
    :class:`str`
        The formatted string.
    """
    return f"</{name}:{id}>"


def get_cog_names() -> List[str]:
    """Get the names of every cog/extension that should be loaded.

    Returns
    -------
    List[:class:`str`]
        The cogs/extensions that should be loaded with `load_extension`.
    """
    return [ext_name for ext_name in disnake.utils.search_directory("cogs")]


##*************************************************##
##********          PROJECT UTILS           *******##
##*************************************************##


def twos_complement(hexstr: str, bits: int):
    value = int(hexstr, 16)  # convert hexadecimal to integer

    # convert from unsigned number to signed number with "bits" bits
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value


def text_post_processing(text: str) -> str:
    # Remove non-ASCII characters
    logger.debug(f"Original text: {text}")
    text = "".join([c if ord(c) < 128 else "" for c in text]).strip()
    logger.debug(f"ASCII text: {text}")

    # Correct spelling https://github.com/filyp/autocorrect#ocr
    spell = autocorrect.Speller(only_replacements=True)
    logger.debug(f"Pre-corrected text: {spell(text)}")
    text = spell(text)
    logger.debug(f"Corrected text: {text}")

    return text


def get_content_type(attachment: disnake.Attachment) -> str:
    if attachment.content_type is None:
        if attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
            return f"image/{attachment.filename.split('.')[-1]}"
        elif attachment.filename.lower().endswith((".mp4", ".webm", ".mov")):
            return f"video/{attachment.filename.split('.')[-1]}"
    elif is_image_content_type(attachment.content_type) or is_video_content_type(
        attachment.content_type
    ):
        return attachment.content_type
    return None


def is_image_content_type(content_type: str) -> bool:
    return content_type.startswith("image")


def is_video_content_type(content_type: str) -> bool:
    return content_type.startswith("video")
