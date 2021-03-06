from typing import Optional

from subot.ocr import detect_green_text, OCR, detect_dialog_text_both_frames, extract_top_right_title_text, OCRResult
from subot.settings import Config
from subot.ui_areas.CodexGeneric import detect_any_text
from subot.ui_areas.base import SpeakAuto, OCRMode, FrameInfo, SpeakCapability
from numpy.typing import NDArray


def anointment_info_extract(gray_frame: NDArray, ocr_engine: OCR) -> str:
    result = detect_any_text(gray_frame, ocr_engine, x_start=0.48, x_end=1.0, y_start=0.09, y_end=1.0)
    text = result.merged_text
    return text


class AnointmentClaimUI(SpeakAuto):
    mode = OCRMode.ANOINTMENT_CLAIM

    def __init__(self, audio_system: SpeakCapability, config: Config, ocr_engine: OCR):
        super().__init__(ocr_engine, config, audio_system)

        self.prev_auto_text_result: Optional[OCRResult] = None
        self.auto_text_result: Optional[OCRResult] = None
        self.auto_text: str = ""
        self.side_extract = anointment_info_extract
        self.interactive_text: str = ""
        self.help_text = f"press {self.program_config.read_secondary_key} for anointment info."
        self.previous_dialog_text: str = ""
        self.current_dialog_text: str = ""

    def _should_speak_dialog(self) -> bool:
        if not self.current_dialog_text:
            return False
        if self.current_dialog_text == self.previous_dialog_text:
            return False
        return True

    def ocr(self, parent: FrameInfo):
        self.prev_auto_text = self.auto_text
        left_box_area = detect_green_text(parent.frame, y_start=0.0, y_end=1, x_start=0.00, x_end=0.465)
        left_box_text = self.ocr_engine.recognize_cv2_image(left_box_area)
        self.prev_auto_text_result = self.auto_text_result
        self.auto_text_result = left_box_text
        self.auto_text = left_box_text.merged_text
        result = self.side_extract(parent.gray_frame, self.ocr_engine)

        self.previous_dialog_text = self.current_dialog_text
        self.current_dialog_text = detect_dialog_text_both_frames(parent.frame, parent.gray_frame, self.ocr_engine)

        self.interactive_text = result

    def _same_menu_item(self) -> bool:
        if not self.prev_auto_text_result:
            return False
        if not self.auto_text_result:
            return False

        # temp fix until proper check for empty results on both
        try:
            return self.prev_auto_text_result.lines[0].first_word().bounding_rect.y == self.auto_text_result.lines[0].first_word().bounding_rect.y
        except IndexError:
            return False

    def speak_auto(self):
        if self._should_speak_dialog():
            text = self.current_dialog_text
            self.audio_system.speak_nonblocking(text)
            return text
        if not self.auto_text:
            return
        if self._same_menu_item():
            return
        text = f"{self.auto_text}. {self.help_text_for_auto()}"
        self.audio_system.speak_nonblocking(text)
        self.first_use = False

    def speak_interaction(self) -> str:
        self.audio_system.speak_nonblocking(self.interactive_text)
        return self.interactive_text
