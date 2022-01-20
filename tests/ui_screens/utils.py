from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
from numpy.typing import NDArray


class AudioSystemTest:
    def __init__(self):
        self.texts: list[str] = []
        self.silence_count: int = 0

    @property
    def last_text(self) -> str:
        return self.texts[-1]

    def speak_nonblocking(self, text: str):
        self.texts.append(text)

    def speak_blocking(self, text: str):
        self.texts.append(text)

    def silence(self):
        self.silence_count += 1


@dataclass
class FrameHolderTest:
    frame: NDArray
    gray_frame: NDArray

def frame_holder_from_fp(path: Path) -> FrameHolderTest:
    img_color = cv2.imread(path.as_posix(), cv2.IMREAD_UNCHANGED)
    img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGRA2GRAY)
    return FrameHolderTest(img_color, img_gray)


class FrameHolderProtocol(Protocol):
    frame: NDArray
    gray_frame: NDArray


class OCRSystemProtocol(Protocol):
    def ocr(self, parent: FrameHolderProtocol):
        pass


def ocr_test_frame(path: Path, system: OCRSystemProtocol):
    frame_holder = frame_holder_from_fp(path)
    system.ocr(frame_holder)
