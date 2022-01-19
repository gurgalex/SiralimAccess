from __future__ import annotations
from abc import abstractmethod, ABC, ABCMeta
from dataclasses import dataclass, field
from enum import Enum, auto

from numpy.typing import NDArray

from subot.ocr import OCR
from subot.settings import Config
from typing import Protocol, Generic, TypeVar


@dataclass
class RoiPercent:
    x_start: float
    x_end: float
    y_start: float
    y_end: float


class OCRMode(Enum):
    SUMMON = auto()
    UNKNOWN = auto()
    INSPECT = auto()
    INSPECT_SCREEN = auto()
    CREATURES_DISPLAY = auto()
    SELECT_GODFORGE_AVATAR = auto()
    CREATURE_REORDER_SELECT = auto()
    CREATURE_REORDER_WITH = auto()
    # creature menu
    MANAGE_SPELL_GEMS = auto()
    EQUIP_SPELL = auto()

    # codex
    GENERIC_SIDE_MENU_50 = auto()
    CODEX_SPELLS = auto()
    """Screen shown to select realm dept and realm to denter"""
    REALM_SELECT = auto()
    ANOINTMENT_CLAIM = auto()
    FIELD_ITEM = auto()

    # enchanter
    SPELL_CRAFT = auto()
    SPELL_ENCHANT = auto()
    SPELL_CHOOSE_ENCHANTMENT = auto()
    SPELL_DISENCHANT = auto()
    SPELL_UPGRADE = auto()

    # battle
    CAST_BATTLE = auto()

    # refinery
    SPELL_REFINERY = auto()


class FrameInfo(Protocol):
    gray_frame: NDArray
    frame: NDArray


class SpeakCapability(Protocol):
    def speak_nonblocking(self, text: str):
        """Don't block thread speaking"""

    def silence(self):
        """Silence any currently TTS output"""


class SpeakAuto(metaclass=ABCMeta):

    def __init__(self, ocr_engine: OCR, config: Config, audio_system: SpeakCapability, *args, **kwargs):
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

    # _step = None

    # @property
    # def step(self):
    #     return self._step
    #
    # @step.setter
    # def step(self, val):
    #     self._step = val

    def same_ui_screen(self, cls: SpeakAuto):
        return all([self.mode is cls.mode])#, self.step is cls.step])


T = TypeVar("T")


class HasStepProtocol(Protocol):
    _step: Enum[T]


class Step(Generic[T]):

    def __init__(self: HasStepProtocol):
        self._step = self._step
        self.last_step: Enum[T] = self._step

    @property
    def is_same_step(self) -> bool:
        return self._step is self.last_step

    @property
    def step(self) -> Enum[T]:
        return self._step

    @step.setter
    def step(self: HasStepProtocol, val: Enum[T]):
        self.last_step = self._step
        self._step = val
