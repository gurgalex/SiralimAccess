from __future__ import annotations
import asyncio
import base64
import copy
from dataclasses import dataclass
from typing import Optional

import time
import math

import cv2
import numpy as np
import numpy.typing
from numpy.typing import NDArray
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import *
from winrt.windows.security.cryptography import CryptographicBuffer

from logging import getLogger

root = getLogger()


# Modified from https://gist.github.com/dantmnf/23f060278585d6243ffd9b0c538beab2

class Rect:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.width = w
        self.height = h

    def __repr__(self):
        return 'rect(%d, %d, %d, %d)' % (self.x, self.y, self.width, self.height)

    def right(self):
        return self.x + self.width

    def bottom(self):
        return self.y + self.height

    def set_right(self, value):
        self.width = value - self.x

    def set_bottom(self, value):
        self.height = value - self.y


def dump_rect(rtrect: winrt.windows.foundation.Rect) -> Rect:
    return Rect(rtrect.x, rtrect.y, rtrect.width, rtrect.height)


@dataclass
class WordWithBounding:
    bounding_rect: Rect
    text: str


def dump_ocrword(word) -> WordWithBounding:
    return WordWithBounding(bounding_rect=dump_rect(word.bounding_rect), text=word.text)


def merge_words(words: list[WordWithBounding]) -> list[WordWithBounding]:
    if len(words) == 0:
        return words
    new_words = [copy.deepcopy(words[0])]
    words = words[1:]
    for word in words:
        lastnewword = new_words[-1]
        lastnewwordrect = new_words[-1].bounding_rect
        wordrect = word.bounding_rect
        if len(word.text) == 1 and wordrect.x - lastnewwordrect.right() <= wordrect.width * 0.2:
            lastnewword.text += word.text
            lastnewwordrect.x = min((wordrect.x, lastnewwordrect.x))
            lastnewwordrect.y = min((wordrect.y, lastnewwordrect.y))
            lastnewwordrect.set_right(max((wordrect.right(), lastnewwordrect.right())))
            lastnewwordrect.set_bottom(max((wordrect.bottom(), lastnewwordrect.bottom())))
        else:
            new_words.append(copy.deepcopy(word))
    return new_words


@dataclass(frozen=True, eq=True)
class OcrLine:
    text: str
    words: list[WordWithBounding]
    merged_words: list[WordWithBounding]
    merged_text: str


def dump_ocrline(line) -> OcrLine:
    words = list(map(dump_ocrword, line.words))
    merged = merge_words(words)
    joined_text = ' '.join([word.text for word in merged])
    return OcrLine(text=line.text,
                   words=words,
                   merged_words=merged,
                   merged_text=joined_text,
                   )


LINE_MULTIPLIER = 16


def l2r_sort(item: OcrLine):
    y_pos = item.merged_words[0].bounding_rect.y
    x_pos = item.merged_words[0].bounding_rect.x

    nearest_line = LINE_MULTIPLIER * round(y_pos / LINE_MULTIPLIER)

    return nearest_line + x_pos / 99999


@dataclass(frozen=True, eq=True)
class OCRResult:
    text: str
    lines: list[OcrLine]
    merged_text: str


def dump_ocrresult(ocrresult) -> OCRResult:
    lines = list(map(dump_ocrline, ocrresult.lines))
    lines = sorted(lines, key=l2r_sort)
    joined_lines = ' '.join(line.merged_text for line in lines)
    text = joined_lines
    merged_text = joined_lines

    return OCRResult(text=text, lines=lines, merged_text=merged_text)


def ibuffer(s: bytes):
    """create WinRT IBuffer instance from a bytes-like object"""
    return CryptographicBuffer.decode_from_base64_string(base64.b64encode(s).decode('ascii'))


def swbmp_from_cv2_image(img: numpy.typing.NDArray):
    pybuf = img.tobytes()
    rtbuf = ibuffer(pybuf)
    return SoftwareBitmap.create_copy_from_buffer(rtbuf, BitmapPixelFormat.GRAY8, img.shape[1], img.shape[0],
                                                  BitmapAlphaMode.IGNORE)


async def ensure_coroutine(awaitable):
    return await awaitable


def blocking_wait(awaitable):
    return asyncio.run(ensure_coroutine(awaitable))


class LanguageNotInstalledException(Exception):
    pass


ENGLISH_NOT_INSTALLED_EXCEPTION = LanguageNotInstalledException("English United States language pack not installed")


@dataclass(frozen=True, eq=True)
class OCRResultSimple:
    text: str
    lines: list[str]


class OCR:
    def __init__(self):
        lang = Language("en-US")
        if not OcrEngine.is_language_supported(lang):
            raise ENGLISH_NOT_INSTALLED_EXCEPTION
        self.ocr_engine = OcrEngine.try_create_from_language(lang)
        self.results: Optional[OCRResult] = None

    def recognize_cv2_image(self, frame: np.typing.ArrayLike) -> OCRResult:
        swbmp = swbmp_from_cv2_image(frame)
        unprocessed_results = blocking_wait(self.ocr_engine.recognize_async(swbmp))
        results = dump_ocrresult(unprocessed_results)
        self.results = results

        return results


def language_is_installed(lang: str) -> bool:
    lang = Language(lang)
    return OcrEngine.is_language_supported(lang)


def english_installed() -> bool:
    return language_is_installed("en-US")


def detect_green_text(image: np.typing.ArrayLike, x_start: float = 0.0, x_end: float = 1.0, y_start: float = 0.0,
                      y_end: float = 1.0) -> NDArray:
    """Using a source image of RGB color, extract highlighted menu items which are a green color"""
    lower_green = np.array([60, 50, 100])
    upper_green = np.array([60, 255, 255])

    y_start = int(image.shape[0] * y_start)
    y_end = int(image.shape[0] * y_end)
    x_start = int(image.shape[1] * x_start)
    x_end = int(image.shape[1] * x_end)

    roi = image[y_start:y_end, x_start:x_end]
    img = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(img, lower_green, upper_green)
    return mask


def detect_white_text(frame: np.typing.ArrayLike, x_start, x_end, y_start, y_end, resize_factor: int = 1,
                      sensitivity: int = 30) -> np.typing.ArrayLike:
    y_start = int(frame.shape[0] * y_start)
    y_end = int(frame.shape[0] * y_end)
    x_start = int(frame.shape[1] * x_start)
    x_end = int(frame.shape[1] * x_end)

    text_area = frame[y_start:y_end, x_start:x_end]

    if resize_factor > 1:
        text_area = cv2.resize(text_area, (text_area.shape[1] * resize_factor, text_area.shape[0] * resize_factor),
                               interpolation=cv2.INTER_LINEAR)

    img = cv2.cvtColor(text_area, cv2.COLOR_BGR2HLS)
    lower_white = np.array([0, 255 - sensitivity, 0])
    upper_white = np.array([0, 255, 0])
    mask = cv2.inRange(img, lower_white, upper_white)
    return mask


def detect_title(frame: np.typing.ArrayLike) -> np.typing.ArrayLike:
    y_start = 0
    y_end = int(frame.shape[0] * 0.1)
    x_start = int(frame.shape[1] * 0.00)
    x_end = int(frame.shape[1] * 0.995)
    title_area = frame[y_start:y_end, x_start:x_end]

    img = cv2.cvtColor(title_area, cv2.COLOR_BGR2HLS)
    sensitivity = 30
    lower_white = np.array([0, 255 - sensitivity, 0])
    upper_white = np.array([0, 255, 0])
    mask = cv2.inRange(img, lower_white, upper_white)
    return mask


def timeit(func):
    def wrap_timer(*args, **kwargs):
        t1 = time.time()
        value = func(*args, **kwargs)
        t2 = time.time()
        took = t2 - t1
        print(f"{func.__name__!r} took {math.ceil(took * 1000)}ms")
        return value

    return wrap_timer


def detect_dialog_text(frame: NDArray, gray_frame: NDArray, ocr_engine: OCR) -> Optional[str]:
    """detect dialog text from frame

    :param gray_frame BGR whole window frame
    :param ocr_engine: engine that can perform OCR on image
    """
    y_start = int(gray_frame.shape[0] * 0.70)
    y_end = int(gray_frame.shape[0] * 0.95)
    x_start = int(gray_frame.shape[1] * 0.01)
    x_end = int(gray_frame.shape[1] * 0.995)
    dialog_area = frame[y_start:y_end, x_start:x_end]
    # output = np.ones(dialog_area.shape, dtype='uint8')
    # output[dialog_area > 180] = 255
    # mask = output

    img = cv2.cvtColor(dialog_area, cv2.COLOR_BGR2HLS)
    sensitivity = 30
    lower_white = np.array([0, 255 - sensitivity, 0])
    upper_white = np.array([0, 255, 0])
    mask = cv2.inRange(img, lower_white, upper_white)

    # resize_factor = 2
    # mask = cv2.resize(mask, (mask.shape[1] * resize_factor, mask.shape[0] * resize_factor),
    #                   interpolation=cv2.INTER_LINEAR)
    ocr_result = ocr_engine.recognize_cv2_image(mask)
    try:
        first_line = ocr_result.lines[0]
        first_word = first_line.words[0]
        bbox = first_word.bounding_rect
        root.debug(f"dialog box: {ocr_result.text}")

        # health bar text - rect(69, 87, 73, 16), rect(282, 87, 71, 16)
        # dialog box text - rect(14, 23, 75, 16)

        offset_x = mask.shape[0] * 0.40
        root.debug(f"{offset_x=}")
        is_not_dialog_box = bbox.x > offset_x
        root.debug(f"{is_not_dialog_box=}")
        if is_not_dialog_box:
            return None
        return ocr_result.merged_text
        # if is_not_dialog_box and not self.has_menu_entry_text:
        #     return
    except IndexError:
        root.debug("no dialog text")
        return None
        # no text was found
        if not self.has_menu_entry_text and not self.has_dialog_text and not self.quest_text:
            root.info("Pause, menu system. both not present")
            self.audio_system.silence()
        return
