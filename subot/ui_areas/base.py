from __future__ import annotations
from abc import abstractmethod, ABC, ABCMeta
from enum import Enum, auto

from numpy.typing import NDArray

from subot.ocr import OCR
from subot.settings import Config
from typing import Protocol


class OCRMode(Enum):
    SUMMON = auto()
    UNKNOWN = auto()
    INSPECT = auto()
    INSPECT_SCREEN = auto()
    CREATURES_DISPLAY = auto()
    SELECT_GODFORGE_AVATAR = auto()
    CREATURE_REORDER_SELECT = auto()
    CREATURE_REORDER_WITH = auto()
    GENERIC_SIDE_MENU_50 = auto()
    """Screen shown to select realm dept and realm to denter"""
    REALM_SELECT = auto()
    ANOINTMENT_CLAIM = auto()


class FrameInfo(Protocol):
    gray_frame: NDArray
    frame: NDArray


class SpeakCapability(Protocol):
    def speak_nonblocking(self, text: str):
        """Don't block thread speaking"""

    def silence(self):
        """Silence any currently TTS output"""


class SpeakAuto(metaclass=ABCMeta):

    def __init__(self, ocr_engine: OCR, config: Config, audio_system: SpeakCapability):
        self.help_text: str = ""
        self.first_use: bool = True
        self.prev_auto_text: str = ""
        self.auto_text: str = ""
        self.ocr_engine: OCR = ocr_engine
        self.program_config: Config = config
        self.audio_system = audio_system

    @property
    @abstractmethod
    def mode(self) -> OCRMode:
        return OCRMode.UNKNOWN

    def help_text_for_auto(self) -> str:
        if self.first_use:
            return self.help_text
        else:
            return ""

    def speak_auto(self):
        if not self.auto_text:
            return
        if self.prev_auto_text == self.auto_text:
            return
        text = f"{self.auto_text}. {self.help_text_for_auto()}"
        self.audio_system.speak_nonblocking(text)
        self.first_use = False

    @abstractmethod
    def ocr(self, parent: FrameInfo):
        pass

    def speak_help(self):
        self.audio_system.speak_nonblocking(self.help_text)

    _step = None

    @property
    def step(self):
        return self._step
    @step.setter
    def step(self, val):
        self._step = val

    def same_ui_screen(self, cls: SpeakAuto):
        return all([self.mode is cls.mode, self.step is cls.step])








