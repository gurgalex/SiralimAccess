from typing import Optional

from .base import SpeakAuto, FrameInfo, OCRMode
from .shared import detect_creature_party_selection
from subot.audio import AudioSystem
from subot.ocr import OCR
from subot.settings import Config
import numpy


class OCRGodForgeSelectSystem(SpeakAuto):
    mode = OCRMode.SELECT_GODFORGE_AVATAR

    def __init__(self, audio_system: AudioSystem, config: Config, ocr_engine: OCR):
        self.auto_text: str = ""
        self.audio_system = audio_system
        self.program_config = config
        self.ocr_engine = ocr_engine
        self.prev_creature_pos: Optional[int] = None
        self.creature_pos: Optional[int] = None

    def ocr(self, parent: FrameInfo):
        self.prev_creature_pos = self.creature_pos
        self.creature_pos = detect_creature_party_selection(parent.frame)

    def speak_auto(self):
        if self.creature_pos != self.prev_creature_pos:
            text = f"Creature {self.creature_pos}, selected to GodForge"
            self.audio_system.speak_nonblocking(text)
