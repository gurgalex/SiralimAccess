from enum import Enum, auto
from typing import Optional

from numpy.typing import NDArray

from subot.ocr import OCR, detect_title_resized_text, detect_green_text
from subot.settings import Config
from subot.ui_areas.base import SpeakAuto, OCRMode, SpeakCapability, Step
from subot.ui_areas.base import FrameInfo
from subot.ocr import slice_img
from subot.ui_areas.enchanter.spell_craft_screen import center_crop

from subot.ui_areas.spell_components import ComponentSortUI, ComponentSpellDescription, ComponentSpellInfo, \
    ComponentSpellEnchanterDescription, ComponentDialogBox, ComponentSpellProperties, enchantment_property_number_text, \
    enchantment_empty_slots_text


class SpellChooseEnchantmentUI(SpeakAuto):
    mode = OCRMode.SPELL_CHOOSE_ENCHANTMENT

    def __init__(self, ocr_engine: OCR, config: Config, audio_system: SpeakCapability):
        super().__init__(ocr_engine, config, audio_system)

        self.description_component = ComponentSpellEnchanterDescription(self.ocr_engine)
        self.spell_properties_component = ComponentSpellProperties(self.ocr_engine)
        self.prev_enchantment_name: str = ""
        self.enchantment_name: str = ""
        self.dialog_box_component = ComponentDialogBox(self.ocr_engine)

        self.help_text = f"Press {self.program_config.read_secondary_key} for spell description and read current properties"

    def ocr(self, parent: FrameInfo):
        bgr = parent.frame
        gray = parent.gray_frame
        ui_border = center_crop(gray, 21)
        bgr_cropped = bgr[ui_border.top:ui_border.bottom, ui_border.left:ui_border.right]

        self.dialog_box_component.ocr(bgr_cropped)
        if self.dialog_box_component.dialog_text:
            return

        spell_name_roi = slice_img(bgr_cropped, x_start=0.00, x_end=0.45, y_start=0.00, y_end=1.0)
        spell_description_roi = slice_img(bgr_cropped, x_start=0.46, x_end=1.0, y_start=0.09, y_end=0.9)
        spell_properties_roi = slice_img(bgr_cropped, x_start=0.47, x_end=1.0, y_start=0.55, y_end=0.85)
        self.spell_properties_component.ocr(spell_properties_roi)

        self.prev_enchantment_name = self.enchantment_name
        self.enchantment_name = self.ocr_engine.recognize_cv2_image(detect_green_text(spell_name_roi)).merged_text

        self.description_component.ocr(spell_description_roi)

    def speak_interaction(self):
        text = f"{self.spell_properties_component.text} \nspell description: {self.description_component.description}\n {self.enchantment_name}"
        self.audio_system.speak_nonblocking(text)

    @property
    def is_same_state(self) -> bool:
        if self.dialog_box_component.dialog_text:
            return self.dialog_box_component.is_same_state

        return self.enchantment_name == self.prev_enchantment_name and self.spell_properties_component.is_same_state

    def speak_auto(self):
        if self.is_same_state:
            return

        if text := self.dialog_box_component.dialog_text:
            self.audio_system.speak_nonblocking(text)
            return

        enchantment_text = f"{self.enchantment_name}, {enchantment_empty_slots_text(self.spell_properties_component)}"

        text = f"{enchantment_text}"
        self.audio_system.speak_nonblocking(text)
