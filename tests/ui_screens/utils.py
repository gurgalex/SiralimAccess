from dataclasses import dataclass

from numpy.typing import NDArray


class AudioSystemTest:
    def __init__(self):
        self.texts: list[str] = []
        self.silence_count: int = 0

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