from typing import Optional

from numpy.typing import NDArray

from subot.ocr import detect_green_text, detect_white_text, OCR, detect_dialog_text_both_frames, OCRResult
from subot.settings import Config
from enum import Enum, auto
from logging import getLogger

from subot.ui_areas.CodexGeneric import detect_any_text
from subot.ui_areas.base import SpeakAuto, FrameInfo, OCRMode, SpeakCapability
from subot.ui_areas.shared import detect_creature_party_selection

root = getLogger()


class UIPart(Enum):
    FIELD_SELECT = auto()
    USE = auto()
    CREATURE_SELECT = auto()
    DIALOG = auto()


class FieldItemSelectUI(SpeakAuto):
    """System active when the 6 creature display is open
    Discarded when closed

    """
    mode = OCRMode.FIELD_ITEM

    def __init__(self, audio_system: SpeakCapability, config: Config, ocr_engine: OCR):

        super().__init__(ocr_engine, config, audio_system)
        self.prev_menu_text: Optional[str] = None
        self.auto_text_result: Optional[OCRResult] = None
        self.auto_text: Optional[str] = None
        self.left_side_text: str = ""
        self.prev_left_side_text: str = ""

        self.right_side_text: str = ""
        self.prev_right_side_text: str = ""

        self.creature_position: Optional[int] = None
        self.prev_creature_position: Optional[int] = None
        self.current_dialog_text: str = ""
        self.previous_dialog_text: str = ""

        self.help_text = f"Press {self.program_config.read_secondary_key} to read field item info"
        self.prev_ui_part: Optional[UIPart] = None
        self.ui_part: UIPart = UIPart.FIELD_SELECT

    def _creature_select_spoken_text(self) -> str:
        return f"Apply to {self.creature_position}"

    def speak_auto(self) -> str:
        if self.same_screen:
            return ""

        text = None
        if self.ui_part is UIPart.DIALOG:
            text = self.current_dialog_text
        elif self.ui_part is UIPart.FIELD_SELECT:
            text = self.left_side_text
        elif self.ui_part is UIPart.CREATURE_SELECT:
            text = self._creature_select_spoken_text()
        elif self.ui_part is UIPart.USE:
            text = "Use it"
        if not text:
            return ""
        self.audio_system.speak_nonblocking(text)
        return text

    @property
    def same_screen(self) -> bool:
        if self.ui_part != self.prev_ui_part:
            return False

        if self.ui_part is UIPart.FIELD_SELECT:
            return self.left_side_text == self.prev_left_side_text
        elif self.ui_part is UIPart.DIALOG:
            return self.current_dialog_text == self.previous_dialog_text
        elif self.ui_part is UIPart.CREATURE_SELECT:
            return self.creature_position == self.prev_creature_position
        elif self.ui_part is UIPart.USE:
            return self.right_side_text == self.prev_right_side_text

    def _analyze(self):
        self.prev_ui_part = self.ui_part
        if self.current_dialog_text:
            self.ui_part = UIPart.DIALOG
            return

        if self.creature_position:
            self.ui_part = UIPart.CREATURE_SELECT
            return

        if self.right_side_text.startswith("What do you want to do"):
            self.ui_part = UIPart.USE
            return

        if self.left_side_text:
            self.ui_part = UIPart.FIELD_SELECT
            return

    def _ocr_left_side(self, frame: NDArray, gray_frame: NDArray):
        left_mask = detect_green_text(image=frame, x_start=0.02, x_end=0.55, y_start=0.08, y_end=1.0)
        text_result = self.ocr_engine.recognize_cv2_image(left_mask)
        self.prev_left_side_text = self.left_side_text
        self.left_side_text = text_result.merged_text

    def _ocr_right_side(self, frame: NDArray, gray_frame: NDArray):
        text_result = detect_any_text(gray_frame=gray_frame, ocr_engine=self.ocr_engine, x_start=0.55, x_end=0.99, y_start=0.08, y_end=0.85)
        self.prev_right_side_text = self.right_side_text
        self.right_side_text = text_result.merged_text

    def _update_dialog_text(self, text: str):
        self.previous_dialog_text = self.current_dialog_text
        self.current_dialog_text = text

    def _update_creature_pos(self, pos: Optional[int]):
        self.prev_creature_position = self.creature_position
        self.creature_position = pos

    def speak_interaction(self) -> str:
        self.audio_system.speak_nonblocking(self.right_side_text)
        return self.right_side_text

    def ocr(self, parent: FrameInfo):
        self._ocr_left_side(parent.frame, parent.gray_frame)
        self._ocr_right_side(parent.frame, parent.gray_frame)

        dialog_text = detect_dialog_text_both_frames(parent.frame, parent.gray_frame, self.ocr_engine)
        self._update_dialog_text(dialog_text)

        pos = detect_creature_party_selection(parent.frame)
        self._update_creature_pos(pos)

        self._analyze()
