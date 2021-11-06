from abc import abstractmethod, ABC, ABCMeta
from enum import Enum, auto
from typing import Protocol

from numpy.typing import NDArray


class OCRMode(Enum):
    SUMMON = auto()
    UNKNOWN = auto()
    INSPECT = auto()
    CREATURES_DISPLAY = auto()
    SELECT_GODFORGE_AVATAR = auto()
    CREATURE_REORDER_SELECT = auto()
    CREATURE_REORDER_WITH = auto()
    """Screen shown to select realm dept and realm to denter"""
    REALM_SELECT = auto()


class FrameInfo(Protocol):
    gray_frame: NDArray
    frame: NDArray


class SpeakAuto(metaclass=ABCMeta):

    @property
    @abstractmethod
    def mode(self) -> OCRMode:
        return OCRMode.UNKNOWN

    @abstractmethod
    def speak_auto(self):
        pass

    @abstractmethod
    def ocr(self, parent: FrameInfo):
        pass

    _step = None

    @property
    def step(self):
        return self._step
    @step.setter
    def step(self, val):
        self._step = val



