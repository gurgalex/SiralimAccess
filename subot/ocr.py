from __future__ import annotations
import asyncio
import base64
import copy
from collections import defaultdict
from concurrent import futures
from dataclasses import dataclass
from typing import Optional

import time
import math

import cv2
import numpy as np
import numpy.typing
from numpy.typing import NDArray
from more_itertools import windowed
import statistics

from logging import getLogger


root = getLogger()


# Modified from https://gist.github.com/dantmnf/23f060278585d6243ffd9b0c538beab2

@dataclass
class Rect:
    x: int
    y: int
    width: int
    height: int

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

    @classmethod
    def new_line(cls, x_pos: int, y_pos: int, line_height: int) -> WordWithBounding:
        rect = Rect(x_pos, y_pos, 0, line_height)
        return cls(rect, "\n")


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

    def first_word(self) -> Optional[WordWithBounding]:
        if not self.words:
            return
        return self.merged_words[0]

    @classmethod
    def new_line(cls, x_pos: int, y_pos: int, line_height: int) -> OcrLine:
        word_new_line = WordWithBounding.new_line(x_pos, y_pos, line_height)
        return cls("\n", [word_new_line], [word_new_line], "\n")


def dump_ocrline(line) -> OcrLine:
    words = list(map(dump_ocrword, line.words))
    merged = merge_words(words)
    joined_text = ' '.join([word.text for word in merged])
    return OcrLine(text=line.text,
                   words=words,
                   merged_words=merged,
                   merged_text=joined_text,
                   )


LINE_MULTIPLIER = 32


def l2r_sort(line: OcrLine):
    first_word = line.first_word()
    y_pos = first_word.bounding_rect.y
    x_pos = first_word.bounding_rect.x

    nearest_line = LINE_MULTIPLIER * math.floor(y_pos / LINE_MULTIPLIER)
    # print(f"nearest line = {nearest_line}, text={line.merged_text}")

    return nearest_line + x_pos / 99999


@dataclass(frozen=True, eq=True)
class OCRResult:
    text: str
    lines: list[OcrLine]
    merged_text: str


def fix_line_alignment(lines: list[OcrLine]) -> list[OcrLine]:
    # for line in lines:
    #     print(f"y_pos={line.first_word().bounding_rect.y}, text={line.merged_text}")
    same_line_ordering: dict[int, list[OcrLine]] = defaultdict(list)
    if len(lines) <= 2:
        return lines
    y_lines = [line.words[0].bounding_rect.height for line in lines]
    median_line_len = statistics.median(y_lines)

    previous_line_y_pos = lines[0].first_word().bounding_rect.y
    same_line_ordering[lines[0].first_word().bounding_rect.y].append(lines[0])

    for idx_current, (current_line, next_line) in enumerate(windowed(lines, n=2, step=1)):
        current_line_rect = current_line.words[0].bounding_rect
        next_line_rect = next_line.words[0].bounding_rect
        line_space: int = next_line_rect.y - current_line_rect.y
        if line_space > median_line_len//1.5:
            previous_line_y_pos = next_line.first_word().bounding_rect.y
        if line_space > median_line_len*3:
            new_line = OcrLine.new_line(current_line_rect.x, current_line_rect.y, previous_line_y_pos+median_line_len)
            same_line_ordering[new_line.first_word().bounding_rect.y].append(new_line)
        same_line_ordering[previous_line_y_pos].append(next_line)

    # sort lines
    final_output = []
    for y_pos, vals in same_line_ordering.items():
        words = []
        text = []
        for line in vals:
            for word in line.words:
                word.bounding_rect.y = y_pos
                words.append(word)
            text.append(line.merged_text)
        vals.sort(key=l2r_sort)
        combined_merged_text = ' '.join(text)
        combined_line = OcrLine(combined_merged_text, words,words, combined_merged_text)
        final_output.append(combined_line)
    return final_output


def dump_ocrresult(ocrresult) -> OCRResult:
    lines = list(map(dump_ocrline, ocrresult.lines))
    lines = sorted(lines, key=l2r_sort)
    lines = fix_line_alignment(lines)
    joined_lines = ' '.join(line.merged_text for line in lines)
    text = joined_lines
    merged_text = joined_lines
    return OCRResult(text=text, lines=lines, merged_text=merged_text)


def swbmp_from_cv2_image(img: numpy.typing.NDArray):
    from winrt.windows.graphics.imaging import SoftwareBitmap, BitmapAlphaMode, BitmapPixelFormat
    from winrt.windows.security.cryptography import CryptographicBuffer
    pybuf = img.tobytes()
    """create WinRT IBuffer instance from a bytes-like object"""
    rtbuf = CryptographicBuffer.decode_from_base64_string(base64.b64encode(pybuf).decode('ascii'))
    return SoftwareBitmap.create_copy_from_buffer(rtbuf, BitmapPixelFormat.GRAY8, img.shape[1], img.shape[0],
                                                  BitmapAlphaMode.IGNORE)


# async def ensure_coroutine(awaitable):
#     return await awaitable
#
#
# def blocking_wait(awaitable):
#     return asyncio.run(ensure_coroutine(awaitable))


class LanguageNotInstalledException(Exception):
    pass


ENGLISH_NOT_INSTALLED_EXCEPTION = LanguageNotInstalledException("English United States language pack not installed")


@dataclass(frozen=True, eq=True)
class OCRResultSimple:
    text: str
    lines: list[str]


class OCR:
    def __init__(self):
        # copied from https://github.com/wolfmanstout/screen-ocr/blob/master/screen_ocr/_winrt.py

        # Run all winrt interactions on a new thread to avoid
        # "RuntimeError: Cannot change thread mode after it is set."
        # from import winrt.
        self._executor = futures.ThreadPoolExecutor(max_workers=1)
        self._executor.submit(self._init_winrt).result()


        # lang = Language("en-US")
        # if not OcrEngine.is_language_supported(lang):
        #     raise ENGLISH_NOT_INSTALLED_EXCEPTION
        # self.ocr_engine = OcrEngine.try_create_from_language(lang)

    def _init_winrt(self):
        import winrt
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.globalization import Language
        from winrt.windows.security.cryptography import CryptographicBuffer

        import winrt.windows.graphics.imaging as imaging
        import winrt.windows.storage.streams as streams

        lang = Language("en-US")
        if not OcrEngine.is_language_supported(lang):
            raise ENGLISH_NOT_INSTALLED_EXCEPTION
        self.ocr_engine = OcrEngine.try_create_from_language(lang)

    async def _recognize_cv2_image(self, frame: np.typing.NDArray) -> OCRResult:
        swbmp = swbmp_from_cv2_image(frame)
        unprocessed_results = await self.ocr_engine.recognize_async(swbmp)
        results = dump_ocrresult(unprocessed_results)

        return results

    def language_is_installed(self, lang: str) -> bool:
        from winrt.windows.globalization import Language
        lang = Language(lang)
        return self.ocr_engine.is_language_supported(lang)

    def english_installed(self) -> bool:
        is_installed = self.language_is_installed("en-US")
        return is_installed

    def recognize_cv2_image(self, frame: np.typing.NDArray) -> OCRResult:
        return self._executor.submit(lambda: asyncio.run(self._recognize_cv2_image(frame))).result()


def extract_top_right_title_text(image: np.typing.ArrayLike, ocr_engine: OCR) -> str:
    text_area_top_right = slice_img(image, x_start=0.75, x_end=0.99, y_start=0.00, y_end=0.09)
    ocr_result = ocr_engine.recognize_cv2_image(text_area_top_right)
    text = ocr_result.merged_text
    return text


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


def slice_img(frame: np.typing.NDArray, x_start: float, x_end: float, y_start: float, y_end: float, resize_factor: int=1) -> np.typing.NDArray:
    y_start = int(frame.shape[0] * y_start)
    y_end = int(frame.shape[0] * y_end)
    x_start = int(frame.shape[1] * x_start)
    x_end = int(frame.shape[1] * x_end)

    text_area = frame[y_start:y_end, x_start:x_end]

    if resize_factor > 1:
        text_area = cv2.resize(text_area, (text_area.shape[1] * resize_factor, text_area.shape[0] * resize_factor),
                               interpolation=cv2.INTER_LINEAR)
    return text_area


def detect_white_text(frame: np.typing.NDArray, x_start: float, x_end: float, y_start: float, y_end: float, resize_factor: int=1,
                      sensitivity: int = 30) -> np.typing.NDArray:
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
    x_end = int(frame.shape[1] * 0.75)
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

    img = cv2.cvtColor(dialog_area, cv2.COLOR_BGR2HLS)
    sensitivity = 30
    lower_white = np.array([0, 255 - sensitivity, 0])
    upper_white = np.array([0, 255, 0])
    mask = cv2.inRange(img, lower_white, upper_white)

    ocr_result = ocr_engine.recognize_cv2_image(mask)
    try:
        first_line = ocr_result.lines[0]
        first_word = first_line.words[0]
        bbox = first_word.bounding_rect
        root.debug(f"dialog box: {ocr_result.text}")

        # health bar text - rect(69, 87, 73, 16), rect(282, 87, 71, 16)
        # dialog box text - rect(14, 23, 75, 16)

        exceeds_dialog_start_x_boundry = bbox.x > mask.shape[1] * 0.04
        exceeds_dialog_start_y_boundry = bbox.y > mask.shape[0] * 0.8
        is_not_dialog_box = exceeds_dialog_start_x_boundry or exceeds_dialog_start_y_boundry
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
