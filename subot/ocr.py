from __future__ import annotations
import asyncio
import base64
import copy

import cv2
import numpy as np
import numpy.typing
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import *
from winrt.windows.security.cryptography import CryptographicBuffer

from enum import Enum, auto


class OCRMode(Enum):
    SUMMON = auto()
    UNKNOWN = auto()
    INSPECT = auto()


class rect:
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


def dump_rect(rtrect: winrt.windows.foundation.Rect):
    return rect(rtrect.x, rtrect.y, rtrect.width, rtrect.height)


def dump_ocrword(word):
    return {
        'bounding_rect': dump_rect(word.bounding_rect),
        'text': word.text
    }


def merge_words(words):
    if len(words) == 0:
        return words
    new_words = [copy.deepcopy(words[0])]
    words = words[1:]
    for word in words:
        lastnewword = new_words[-1]
        lastnewwordrect = new_words[-1]['bounding_rect']
        wordrect = word['bounding_rect']
        if len(word['text']) == 1 and wordrect.x - lastnewwordrect.right() <= wordrect.width * 0.2:
            lastnewword['text'] += word['text']
            lastnewwordrect.x = min((wordrect.x, lastnewwordrect.x))
            lastnewwordrect.y = min((wordrect.y, lastnewwordrect.y))
            lastnewwordrect.set_right(max((wordrect.right(), lastnewwordrect.right())))
            lastnewwordrect.set_bottom(max((wordrect.bottom(), lastnewwordrect.bottom())))
        else:
            new_words.append(copy.deepcopy(word))
    return new_words


def dump_ocrline(line):
    words = list(map(dump_ocrword, line.words))
    merged = merge_words(words)
    return {
        'text': line.text,
        'words': words,
        'merged_words': merged,
        'merged_text': ' '.join(map(lambda x: x['text'], merged))
    }

LINE_MULTIPLIER = 16

def l2r_sort(item: dict):
    y_pos = item['merged_words'][0]['bounding_rect'].y
    x_pos = item['merged_words'][0]['bounding_rect'].x

    nearest_line = LINE_MULTIPLIER * round(y_pos/LINE_MULTIPLIER)

    return nearest_line + x_pos/99999


def dump_ocrresult(ocrresult):
    lines = list(map(dump_ocrline, ocrresult.lines))
    lines = sorted(lines, key=l2r_sort)

    return {
        'text': ocrresult.text,
        # 'text_angle': ocrresult.text_angle.value if ocrresult.text_angle else None,
        'lines': lines,
        'merged_text': ' '.join(map(lambda x: x['merged_text'], lines))
    }


def ibuffer(s):
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


class OCR:
    def __init__(self):
        lang = Language("en-US")
        if not OcrEngine.is_language_supported(lang):
            raise LanguageNotInstalledException("English United States language pack not installed")
        self.ocr_engine = OcrEngine.try_create_from_language(lang)


ENGLISH_NOT_INSTALLED_EXCEPTION = LanguageNotInstalledException("English United States language pack not installed")


def language_is_installed(lang: str) -> bool:
    lang = Language(lang)
    return OcrEngine.is_language_supported(lang)


def english_installed() -> bool:
    return language_is_installed("en-US")


def recognize_cv2_image(img):
    language = Language("en-US")
    if not english_installed:
        raise ENGLISH_NOT_INSTALLED_EXCEPTION
    eng = OcrEngine.try_create_from_language(language)
    swbmp = swbmp_from_cv2_image(img)
    return dump_ocrresult(blocking_wait(eng.recognize_async(swbmp)))


def detect_green_text(image: np.typing.ArrayLike, x_start: float = 0.0, x_end: float = 1.0, y_start: float = 0.0, y_end: float = 1.0) -> np.array:
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


def detect_white_text(frame: np.typing.ArrayLike, x_start, x_end, y_start, y_end) -> np.typing.ArrayLike:
    y_start = int(frame.shape[0] * y_start)
    y_end = int(frame.shape[0] * y_end)
    x_start = int(frame.shape[1] * x_start)
    x_end = int(frame.shape[1] * x_end)

    text_area = frame[y_start:y_end, x_start:x_end]

    img = cv2.cvtColor(text_area, cv2.COLOR_BGR2HLS)
    sensitivity = 30
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


def detect_dialog_text(frame: np.typing.ArrayLike) -> np.typing.ArrayLike:
    y_start = int(frame.shape[0] * 0.70)
    y_end = int(frame.shape[0] * 0.95)
    x_start = int(frame.shape[1] * 0.01)
    x_end = int(frame.shape[1] * 0.995)
    dialog_area = frame[y_start:y_end, x_start:x_end]

    img = cv2.cvtColor(dialog_area, cv2.COLOR_BGR2HLS)
    sensitivity = 30
    lower_white = np.array([0, 255 - sensitivity, 0])
    upper_white = np.array([0, 255, 0])
    mask = cv2.inRange(img, lower_white, upper_white)
    return mask
