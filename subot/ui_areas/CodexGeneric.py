from __future__ import annotations
from subot.ocr import OCR, OCRResult, detect_green_text, slice_img, detect_any_text
from subot.settings import Config
from subot.ui_areas.base import SpeakAuto, FrameInfo, OCRMode, SpeakCapability
from numpy.typing import NDArray


def extract_text(ocr_result: OCRResult) -> str:
    if text := ocr_result.merged_text:
        return text
    else:
        return ""


def extract_text_right_side_44(gray_frame: NDArray, engine: OCR) -> str:
    text_ocr_result = detect_any_text(gray_frame, engine, x_start=0.44, x_end=1.00, y_start=0.09, y_end=1.00)
    all_text = text_ocr_result.merged_text
    return all_text


def extract_perk_details_text(gray_frame: NDArray, engine: OCR) -> str:
    text_ocr_result = detect_any_text(gray_frame, engine, x_start=0.48, x_end=1.00, y_start=0.09, y_end=1.00)
    all_text = text_ocr_result.merged_text
    return all_text


class CodexGeneric(SpeakAuto):
    mode = OCRMode.GENERIC_SIDE_MENU_50

    def __init__(self, audio_system: SpeakCapability, config: Config, ocr_engine: OCR, title: str, side_right_text_fn=None):
        super().__init__(ocr_engine, config, audio_system)
        self.auto_text: str = ""
        self.side_extract = side_right_text_fn or extract_text_right_side_44
        self.title = title
        self.interactive_text: str = ""
        self.help_text: str = f"Press {self.program_config.read_secondary_key} for description"

    def ocr(self, parent: FrameInfo):
        self.prev_auto_text = self.auto_text
        left_box_area = detect_green_text(parent.frame, y_start=0.0, y_end=1, x_start=0.00, x_end=0.4)
        left_box_text = self.ocr_engine.recognize_cv2_image(left_box_area)
        self.auto_text = left_box_text.merged_text
        result = self.side_extract(parent.gray_frame, self.ocr_engine)
        self.interactive_text = result

    def speak_interaction(self) -> str:
        self.audio_system.speak_nonblocking(self.interactive_text)
        return self.interactive_text


