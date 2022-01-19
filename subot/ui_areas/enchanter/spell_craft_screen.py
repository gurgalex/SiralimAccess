from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from subot.ocr import OCR
from subot.settings import Config
from subot.ui_areas.base import SpeakAuto, OCRMode, SpeakCapability
from subot.ui_areas.base import FrameInfo
from subot.ocr import slice_img

from subot.ui_areas.spell_components import ComponentSortUI, ComponentSpellDescription, ComponentSpellInfo, \
    ComponentDialogBox


@dataclass
class CropBorder:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


def center_crop(img_gray: NDArray, ui_bg_color: int = 0, matches: bool = False) -> CropBorder:
    try:
        center_y, center_x = img_gray.shape[0]//2, img_gray.shape[1]//2
        center_row = img_gray[center_y:center_y+1, :]
        center_col = img_gray[:, center_x:center_x+1]
        if matches:
            idx_row = np.argwhere(center_row == ui_bg_color)
            idx_col = np.argwhere(center_col == ui_bg_color)
        else:
            idx_row = np.argwhere(center_row != ui_bg_color)
            idx_col = np.argwhere(center_col != ui_bg_color)

        border = CropBorder()
        border.left = idx_row[0][1]
        border.right = idx_row[-1][1]

        border.top = idx_col[0][0]
        border.bottom = idx_col[-1][0]
        return border
    except IndexError:
        print("warning: unable to crop UI. using whole frame")
        return CropBorder()

@dataclass()
class ChildMetadata:
    track_equality: bool = False

@dataclass(frozen=True)
class ChildContainer:
    metadata: ChildMetadata
    child: Any


from typing import Protocol
class SameState(Protocol):
    is_same_state: bool = False

class Base:
    def __init__(self):
        # self.children: dict[int, list[Any]] = defaultdict(list)
        self.same_states: list[SameState] = []

    # def register_component(self, entity: Any, component: Any):
    #     self.children[component].append(entity)

def is_same_spell_ui_state(spell_info_comp: ComponentSpellInfo, sort_comp: ComponentSortUI, dialog_comp: ComponentDialogBox):
    if dialog_comp.dialog_text:
        return dialog_comp.is_same_state
    return spell_info_comp.is_same_state and sort_comp.is_same_state


class SpellCraftUI(SpeakAuto):
    mode = OCRMode.SPELL_CRAFT

    def __init__(self, ocr_engine: OCR, config: Config, audio_system: SpeakCapability):
        super().__init__(ocr_engine, config, audio_system)
        self.description_component = ComponentSpellDescription(self.ocr_engine)
        self.sort_component = ComponentSortUI(self.ocr_engine)
        self.spell_info_component = ComponentSpellInfo(self.ocr_engine)
        self.dialog_box_component = ComponentDialogBox(self.ocr_engine)

        self.help_text = f"Press {self.program_config.read_secondary_key} for description, press f to change sort order of spells"

    def ocr(self, parent: FrameInfo):
        bgr = parent.frame
        gray = parent.gray_frame
        ui_border = center_crop(gray, 21)
        bgr_cropped = bgr[ui_border.top:ui_border.bottom, ui_border.left:ui_border.right]

        self.dialog_box_component.ocr(bgr_cropped)
        if self.dialog_box_component.dialog_text:
            return

        spell_name_roi = slice_img(bgr_cropped, x_start=0.00, x_end=0.45, y_start=0.00, y_end=1.0)
        self.spell_info_component.ocr(spell_name_roi)

        spell_description_roi = slice_img(bgr_cropped, x_start=0.46, x_end=1.0, y_start=0.09, y_end=0.9)
        self.description_component.ocr(spell_description_roi)

        sort_text_roi = slice_img(bgr_cropped, x_start=0.75, x_end=1.0, y_start=0.0, y_end=0.09)
        self.sort_component.ocr(sort_text_roi)

    def speak_interaction(self):
        self.audio_system.speak_nonblocking(self.description_component.description)

    @property
    def is_same_state(self) -> bool:
        if self.dialog_box_component.dialog_text:
            return self.dialog_box_component.is_same_state
        return self.spell_info_component.is_same_state and self.sort_component.is_same_state

    def speak_auto(self):
        if self.is_same_state:
            return

        if text := self.dialog_box_component.dialog_text:
            self.audio_system.speak_nonblocking(text)
            return

        sort_text = self.sort_component.new_text

        spell_gem_text = f"{self.spell_info_component.spell_name}, {self.spell_info_component.spell_class.name} class"

        text = f"{spell_gem_text}. {sort_text}"
        self.audio_system.speak_nonblocking(text)


if __name__ == "__main__":
    from tests.ui_screens.utils import FrameHolderTest, AudioSystemTest
    from subot.settings import Config
    from subot.ocr import OCR

    audio_system = AudioSystemTest()
    ocr_engine = OCR()
    config = Config()
    spell_screen_ui = SpellCraftUI(ocr_engine, config, audio_system)

    # img = cv2.imread("../../tests/ui_screens/spell-craft/chaos.png", cv2.IMREAD_UNCHANGED)
    # gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # frame_info = FrameHolderTest(img, gray)
    # spell_screen_ui.ocr(frame_info)
    # spell_screen_ui.speak_auto()
    #
    # img = cv2.imread("../../tests/ui_screens/spell-craft/chaos_1920.png", cv2.IMREAD_UNCHANGED)
    # gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # frame_info = FrameHolderTest(img, gray)
    # spell_screen_ui.ocr(frame_info)
    # spell_screen_ui.speak_auto()
    #
    # img = cv2.imread("../../tests/ui_screens/spell-craft/death.png", cv2.IMREAD_UNCHANGED)
    # gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # frame_info = FrameHolderTest(img, gray)
    # spell_screen_ui.ocr(frame_info)
    # spell_screen_ui.speak_auto()
    #
    # img = cv2.imread("../../tests/ui_screens/spell-craft/life.png", cv2.IMREAD_UNCHANGED)
    # gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # frame_info = FrameHolderTest(img, gray)
    # spell_screen_ui.ocr(frame_info)
    # spell_screen_ui.speak_auto()

    img = cv2.imread("../../../tests/ui_screens/spell-craft/nature.png", cv2.IMREAD_UNCHANGED)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    frame_info = FrameHolderTest(img, gray)
    spell_screen_ui.ocr(frame_info)
    spell_screen_ui.speak_auto()

    img = cv2.imread("../../../tests/ui_screens/spell-craft/sorcery.png", cv2.IMREAD_UNCHANGED)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    frame_info = FrameHolderTest(img, gray)
    spell_screen_ui.ocr(frame_info)
    spell_screen_ui.speak_auto()

    # not part of test
    img = cv2.imread("../../../tests/ui_screens/spell-cast/nature-ethereal.png", cv2.IMREAD_UNCHANGED)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    frame_info = FrameHolderTest(img, gray)
    spell_screen_ui.ocr(frame_info)
    spell_screen_ui.speak_auto()

    print(audio_system.texts)


