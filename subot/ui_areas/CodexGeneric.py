from __future__ import annotations
from subot.ocr import OCR, OCRResult, detect_green_text, slice_img, detect_any_text
from subot.settings import Config
from subot.ui_areas.base import SpeakAuto, FrameInfo, OCRMode, SpeakCapability, RoiPercent
from numpy.typing import NDArray

from subot.ui_areas.enchanter.spell_craft_screen import center_crop
from subot.ui_areas.spell_components import ComponentSpellDescription, ComponentSpellInfo, ComponentSortUI


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
    LEFT_ROI = RoiPercent(x_start=0.00, x_end=0.4, y_start=0.0, y_end=1)
    RIGHT_ROI = RoiPercent(x_start=0.44, x_end=1.00, y_start=0.09, y_end=1.00)

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
        left_roi = CodexGeneric.LEFT_ROI
        left_box_area = detect_green_text(parent.frame, y_start=left_roi.y_start, y_end=left_roi.y_end, x_start=left_roi.x_start, x_end=left_roi.x_end)
        left_box_text = self.ocr_engine.recognize_cv2_image(left_box_area)
        self.auto_text = left_box_text.merged_text
        result = self.side_extract(parent.gray_frame, self.ocr_engine)
        self.interactive_text = result

    def speak_interaction(self) -> str:
        self.audio_system.speak_nonblocking(self.interactive_text)
        return self.interactive_text


class CodexSpells(CodexGeneric):
    mode = OCRMode.CODEX_SPELLS

    def __init__(self, ocr_engine: OCR, config: Config, audio_system: SpeakCapability, title: str):
        super().__init__(audio_system, config, ocr_engine, title)
        self.description_component = ComponentSpellDescription(self.ocr_engine)
        self.spell_info_component = ComponentSpellInfo(self.ocr_engine)
        self.sort_component = ComponentSortUI(self.ocr_engine)
        self.help_text: str = f"Press {self.program_config.read_secondary_key} for description, press f to search for spell info"

    def ocr(self, parent: FrameInfo):
        bgr = parent.frame
        gray = parent.gray_frame
        ui_border = center_crop(gray, 21)
        bgr_cropped = bgr[ui_border.top:ui_border.bottom, ui_border.left:ui_border.right]

        left_roi = self.LEFT_ROI
        spell_name_roi = slice_img(bgr_cropped, x_start=left_roi.x_start, x_end=left_roi.x_end, y_start=left_roi.y_start, y_end=left_roi.y_end)
        self.spell_info_component.ocr(spell_name_roi)

        right_roi = self.RIGHT_ROI
        spell_description_roi = slice_img(bgr_cropped, x_start=right_roi.x_start, x_end=right_roi.x_end, y_start=right_roi.y_start, y_end=right_roi.y_end)
        self.description_component.ocr(spell_description_roi)

        sort_text_roi = slice_img(bgr_cropped, x_start=0.75, x_end=1.0, y_start=0.0, y_end=0.09)
        self.sort_component.ocr(sort_text_roi)


    def speak_interaction(self):
        self.audio_system.speak_nonblocking(self.description_component.description)

    @property
    def is_same_state(self) -> bool:
        return self.spell_info_component.is_same_state and self.sort_component.is_same_state

    def speak_auto(self):
        if self.is_same_state:
            return

        sort_text = self.sort_component.new_text

        spell_gem_text = f"{self.spell_info_component.spell_name}, {self.spell_info_component.spell_class.name} class"

        text = f"{spell_gem_text}. {sort_text}"
        self.audio_system.speak_nonblocking(text)



# ui_border = center_crop(gray, 21)
