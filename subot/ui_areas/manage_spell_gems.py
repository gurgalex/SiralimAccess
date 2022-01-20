from typing import Optional

import cv2

from subot.ocr import OCR, detect_title, detect_green_text, detect_title_resized_text
from subot.settings import Config
from subot.ui_areas.base import SpeakAuto, OCRMode, SpeakCapability, Step
from subot.ui_areas.base import FrameInfo
from subot.ocr import slice_img
from subot.ui_areas.enchanter.spell_craft_screen import center_crop

from subot.ui_areas.spell_components import ComponentSortUI, ComponentSpellDescription, ComponentSpellInfo, \
    ComponentSpellEnchanterDescription, NoSpellException

from enum import Enum, auto


class StepManageSpell(Enum):
    SELECT_CURRENT = auto()
    OPTIONS = auto()


class ManageSpellGemsUI(SpeakAuto):
    mode = OCRMode.MANAGE_SPELL_GEMS
    CREATURE_NAME_OFFSET: int = len("manage spell gems for your ")

    def __init__(self, ocr_engine: OCR, config: Config, audio_system: SpeakCapability):
        super().__init__(ocr_engine, config, audio_system)
        self.step = StepManageSpell.SELECT_CURRENT
        self.last_step = self.step
        self.prev_title: Optional[str] = None
        self.title = ""
        self.description_component = ComponentSpellEnchanterDescription(self.ocr_engine)
        self.spell_info_component = ComponentSpellInfo(self.ocr_engine)
        self.prev_empty_slot: bool = False
        self.empty_slot: bool = False
        self.help_text = f"Press {self.program_config.read_secondary_key} for spell description and properties"

    def is_same_step(self) -> bool:
        return self.last_step is self.step

    def ocr(self, parent: FrameInfo):
        self.last_step = self.step
        self.step = StepManageSpell.SELECT_CURRENT
        bgr = parent.frame
        gray = parent.gray_frame
        ui_border = center_crop(gray, 21)
        bgr_cropped = bgr[ui_border.top:ui_border.bottom, ui_border.left:ui_border.right]

        title_text_result = detect_title_resized_text(bgr_cropped, self.ocr_engine)
        self.prev_title = self.title
        self.title = title_text_result.merged_text

        spell_description_roi = slice_img(bgr_cropped, x_start=0.55, x_end=1.0, y_start=0.09, y_end=1.0)
        self.description_component.ocr(spell_description_roi)
        spell_name_roi = slice_img(bgr_cropped, x_start=0.00, x_end=0.54, y_start=0.09, y_end=1.0)
        try:
            self.prev_empty_slot = self.empty_slot
            self.spell_info_component.ocr(spell_name_roi)
            self.empty_slot = False
        except NoSpellException:
            name_result = self.ocr_engine.recognize_cv2_image(spell_name_roi)
            if "empty slot" in name_result.merged_text.lower():
                self.empty_slot = True

        if self.description_component.description.startswith("What do you want to do"):
            self.step = StepManageSpell.OPTIONS
            new_text = self.ocr_engine.recognize_cv2_image(detect_green_text(spell_description_roi)).merged_text
            self.prev_auto_text = self.auto_text
            self.auto_text = new_text

    def speak_interaction(self):
        self.audio_system.speak_nonblocking(self.description_component.description)

    @property
    def _same_state_with_empty_slot(self) -> bool:
        return self.empty_slot == self.prev_empty_slot

    @property
    def is_same_state(self) -> bool:
        if not self.is_same_step():
            return False
        if self.step is StepManageSpell.SELECT_CURRENT:
            return self.spell_info_component.is_same_state and self._same_state_with_empty_slot
        elif self.step is StepManageSpell.OPTIONS:
            return self.prev_auto_text == self.auto_text

    def speak_auto(self):
        if self.is_same_state:
            return
        if self.step is StepManageSpell.OPTIONS:
            text = self.auto_text
            self.audio_system.speak_nonblocking(text)
            return

        if self.prev_title != self.title:
            creature_name = f"{self.title[self.CREATURE_NAME_OFFSET:]}, "
        else:
            creature_name = ""
        self.prev_title = self.title

        if self.empty_slot:
            text = f"{creature_name} Empty Slot"
            self.audio_system.speak_nonblocking(text)
            return

        equipped_text = "default" if self.spell_info_component.has_yellow_star else ""
        spell_gem_text = f"{creature_name}{self.spell_info_component.spell_name}, {equipped_text}, {self.spell_info_component.spell_class.name} class"

        text = f"{spell_gem_text}"
        self.audio_system.speak_nonblocking(text)

