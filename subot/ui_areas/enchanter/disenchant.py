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
    ComponentSpellEnchanterDescription, ComponentDialogBox


class DisenchantStep(Enum):
    SELECT_SPELL = auto()
    SLOT_DISENCHANT = auto()


class SpellDisenchantUI(SpeakAuto, Step):
    mode = OCRMode.SPELL_DISENCHANT

    def __init__(self, ocr_engine: OCR, config: Config, audio_system: SpeakCapability):
        super().__init__(ocr_engine, config, audio_system)
        self._step = DisenchantStep.SELECT_SPELL

        self.description_component = ComponentSpellEnchanterDescription(self.ocr_engine)
        # self.spell_properties_component = ComponentSpellProperties(self.ocr_engine)
        self.sort_component = ComponentSortUI(self.ocr_engine)
        self.spell_info_component = ComponentSpellInfo(self.ocr_engine)
        self.dialog_box_component = ComponentDialogBox(self.ocr_engine)

        self.prev_slot_text = ""
        self.slot_text = ""

        self.help_text = f"Press {self.program_config.read_secondary_key} for description, press f to change sort order of spells"

    def detect_step(self, cropped_frame: NDArray) -> Optional[DisenchantStep]:
        title_result_text = detect_title_resized_text(cropped_frame, self.ocr_engine).merged_text
        lower_title = title_result_text.lower()
        if lower_title.startswith("choose a gem to disenchant"):
            return DisenchantStep.SELECT_SPELL
        elif lower_title.startswith("choose a slot to disenchant"):
            return DisenchantStep.SLOT_DISENCHANT

    def ocr(self, parent: FrameInfo):
        bgr = parent.frame
        gray = parent.gray_frame
        ui_border = center_crop(gray, 21)
        bgr_cropped = bgr[ui_border.top:ui_border.bottom, ui_border.left:ui_border.right]
        if step := self.detect_step(bgr_cropped):
            self.step = step
        else:
            return

        spell_name_roi = slice_img(bgr_cropped, x_start=0.00, x_end=0.45, y_start=0.00, y_end=1.0)
        spell_description_roi = slice_img(bgr_cropped, x_start=0.46, x_end=1.0, y_start=0.09, y_end=0.9)
        if self.step is DisenchantStep.SELECT_SPELL:
            self.dialog_box_component.ocr(bgr_cropped)
            if self.dialog_box_component.dialog_text:
                return

            self.spell_info_component.ocr(spell_name_roi)

            self.description_component.ocr(spell_description_roi)

            sort_text_roi = slice_img(bgr_cropped, x_start=0.75, x_end=1.0, y_start=0.0, y_end=0.09)
            self.sort_component.ocr(sort_text_roi)
        elif self.step is DisenchantStep.SLOT_DISENCHANT:
            self.dialog_box_component.ocr(bgr_cropped)
            if self.dialog_box_component.dialog_text:
                return

            self.spell_info_component.ocr(spell_name_roi)

            self.description_component.ocr(spell_description_roi)

            spell_properties_roi = slice_img(bgr_cropped, x_start=0.47, x_end=1.0, y_start=0.55, y_end=0.85)
            properties_text = self.ocr_engine.recognize_cv2_image(detect_green_text(spell_properties_roi)).merged_text
            self.prev_slot_text = self.slot_text
            self.slot_text = properties_text

    def speak_interaction(self):
        if self.step is DisenchantStep.SELECT_SPELL:
            self.audio_system.speak_nonblocking(self.description_component.description)
        elif self.step is DisenchantStep.SLOT_DISENCHANT:
            text = f"{self.description_component.description}"
            self.audio_system.speak_nonblocking(text)

    @property
    def is_same_state(self) -> bool:
        if not self.is_same_step:
            return False
        if self.dialog_box_component.dialog_text:
            return self.dialog_box_component.is_same_state

        if self.step is DisenchantStep.SELECT_SPELL:
            return self.spell_info_component.is_same_state and self.sort_component.is_same_state
        elif self.step is DisenchantStep.SLOT_DISENCHANT:
            return self.slot_text == self.prev_slot_text

    def speak_auto(self):
        if self.is_same_state:
            return

        if text := self.dialog_box_component.dialog_text:
            self.audio_system.speak_nonblocking(text)
            return

        if self.step is DisenchantStep.SELECT_SPELL:
            sort_text = self.sort_component.new_text

            equipped_text = "equipped" if self.spell_info_component.has_yellow_star else ""
            spell_gem_text = f"{self.spell_info_component.spell_name}, {equipped_text}, {self.spell_info_component.spell_class.name} class"

            text = f"{spell_gem_text}. {sort_text}"
            self.audio_system.speak_nonblocking(text)
        elif self.step is DisenchantStep.SLOT_DISENCHANT:
            text = self.slot_text
            self.audio_system.speak_nonblocking(text)

