from typing import Optional


from subot.ocr import OCR, detect_any_text
from subot.settings import Config
import numpy as np
import pyclip as clip
from logging import getLogger

from subot.ui_areas.base import FrameInfo, OCRMode, SpeakAuto, SpeakCapability

root = getLogger()


class InspectScreenUI(SpeakAuto):
    """System active when summoning screen is open
    Discarded when closed

    """
    mode = OCRMode.INSPECT_SCREEN

    def __init__(self, audio_system: SpeakCapability, config: Config, ocr_engine: OCR):
        super().__init__(ocr_engine, config, audio_system)
        self.prev_creature: str = ""
        self.creature_name: str = ""
        self.creature_class: str = ""
        self.creature_race: str = ""
        self.creature_personality: str = ""
        self.creature_stats = ""

        self.prev_right_text_first_line: str = ""
        self.right_text_first_line: str = ""
        self.right_text: str = ""

        self.prev_page_number: str = ""
        self.page_number: str = ""
        # first time UI has been open
        self.help_text = f"Help: {self.program_config.read_secondary_key} for page text. {self.program_config.read_all_info_key} for creature stats"
        self.same_screen: bool = False

    def ocr(self, parent: FrameInfo):
        self._ocr_inspect_ui(parent.frame, parent.gray_frame)

    def speak_auto(self) -> Optional[str]:
        """Text spoken without any user interaction"""
        if not self.same_screen:
            return self.speak_page_text()
        self.first_use = False
        return

    def speak_page_text(self):
        help_text = self.help_text if self.first_use else ""
        creature_name = ""
        if self.creature_name != self.prev_creature:
            creature_name = self.creature_name

        right_text = ""
        if self.prev_right_text_first_line != self.right_text_first_line:
            right_text = self.right_text

        combined_text = f"{creature_name}\n{right_text}. {help_text}"
        self.audio_system.speak_nonblocking(combined_text)
        return combined_text

    def speak_interaction(self) -> str:
        """Speaks text which requires a summary key press"""
        if not self.right_text:
            return ""

        right_text = self.right_text
        self.audio_system.speak_nonblocking(right_text)
        return right_text

    def speak_all_info(self):
        if not self.creature_name:
            return ""

        stats = f"""{self.creature_name}
class: {self.creature_class}: race: {self.creature_race}
personality: {self.creature_personality}
stats: {self.creature_stats}
"""
        self.audio_system.speak_nonblocking(stats)
        return stats

    def detect_left_creature_area(self, frame, gray_frame):

        text_left_area = detect_any_text(gray_frame, ocr_engine=self.ocr_engine, x_start=0.01, x_end=0.48, y_start=0.08, y_end=0.55)

        self.prev_creature = self.creature_name
        try:
            self.creature_name = text_left_area.lines[0].merged_text
        except IndexError:
            self.creature_name = "unknown creature"
        try:
            self.creature_class, self.creature_race = text_left_area.lines[1].merged_text.split(" ", maxsplit=1)
        except ValueError:
            self.creature_class = "unknown"
            self.creature_race = text_left_area.lines[1].merged_text
        except IndexError:
            self.creature_class = "unknown"
            self.creature_race = "unknown"
        try:
            self.creature_personality = text_left_area.lines[2].merged_text
        except IndexError:
            self.creature_personality = "unknown"
        try:
            self.creature_stats = '\n'.join(line.merged_text for line in text_left_area.lines[3:])
        except IndexError:
            self.creature_stats = "unknown"

    def detect_right_text(self, frame, gray_frame):
        right_text = detect_any_text(gray_frame, ocr_engine=self.ocr_engine, x_start=0.47, x_end=1.0, y_start=0.085, y_end=0.985)
        self.prev_right_text_first_line = self.right_text_first_line
        self.right_text = right_text.merged_text
        try:
            self.right_text_first_line = right_text.lines[0].merged_text
        except IndexError:
            self.right_text_first_line = ""

    def _ocr_inspect_ui(self, frame: np.typing.ArrayLike, gray_frame: np.typing.ArrayLike):
        self.detect_left_creature_area(frame, gray_frame)
        self.detect_right_text(frame, gray_frame)
        if not self.right_text or self.right_text_first_line == self.prev_right_text_first_line:
            self.same_screen = True
            return
        self.same_screen = False
