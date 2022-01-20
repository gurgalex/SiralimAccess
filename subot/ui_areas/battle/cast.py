import cv2

from subot.ocr import OCR
from subot.settings import Config
from subot.ui_areas.base import SpeakAuto, OCRMode, SpeakCapability
from subot.ui_areas.base import FrameInfo
from subot.ocr import slice_img
from subot.ui_areas.enchanter.spell_craft_screen import center_crop

from subot.ui_areas.spell_components import ComponentSpellDescription, ComponentSpellInfo


class BattleCastUI(SpeakAuto):
    mode = OCRMode.CAST_BATTLE

    def __init__(self, ocr_engine: OCR, config: Config, audio_system: SpeakCapability):
        super().__init__(ocr_engine, config, audio_system)
        self.description_component = ComponentSpellDescription(self.ocr_engine)
        self.spell_info_component = ComponentSpellInfo(self.ocr_engine)
        self.help_text = f"Press {self.program_config.read_secondary_key} for spell description and properties"

    def ocr(self, parent: FrameInfo):
        bgr = parent.frame
        gray = parent.gray_frame
        ui_border = center_crop(gray, 0, matches=False)
        bgr_cropped = bgr[ui_border.top:ui_border.bottom, ui_border.left:ui_border.right]

        spell_name_roi = slice_img(bgr_cropped, x_start=0.00, x_end=0.39, y_start=0.1, y_end=0.66)
        self.spell_info_component.ocr(spell_name_roi)

        spell_description_roi = slice_img(bgr_cropped, x_start=0.40, x_end=1.0, y_start=0.1, y_end=0.66)
        self.description_component.ocr(spell_description_roi)

    def speak_interaction(self):
        self.audio_system.speak_nonblocking(self.description_component.description)

    @property
    def is_same_state(self) -> bool:
        return self.spell_info_component.is_same_state

    def speak_auto(self):
        if self.is_same_state:
            return

        ethereal_text = "ethereal" if self.spell_info_component.is_ethereal else ""
        spell_gem_text = f"{self.spell_info_component.spell_name}, {ethereal_text}, {self.spell_info_component.spell_class.name} class"

        text = f"{spell_gem_text}"
        self.audio_system.speak_nonblocking(text)

