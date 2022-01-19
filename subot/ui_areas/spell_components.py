from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import cv2
import numpy as np
from numpy.typing import NDArray

from subot.ocr import OCR, detect_green_text, slice_img, detect_dialog_text_color, OCRResult, detect_white_text


class SpellGemClass(Enum):
    CHAOS = auto()
    DEATH = auto()
    SORCERY = auto()
    LIFE = auto()
    NATURE = auto()
    UNKNOWN = auto()


@dataclass(eq=True, frozen=True)
class SpellSelectionInfo:
    spell_name: str
    gem_class: SpellGemClass
    is_ethereal: bool = False
    has_yellow_star: bool = False
    has_exclamation: bool = False

def detect_exclamation(bgr: NDArray) -> bool:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    EXCLAMATION_RANGE_HSV = (np.array([58//2, 255,  255]), np.array([60//2, 255, 255]))
    pixels_exclamation = np.count_nonzero(cv2.inRange(hsv, EXCLAMATION_RANGE_HSV[0], EXCLAMATION_RANGE_HSV[1]))
    return pixels_exclamation > 0


def detect_yellow_star(bgr: NDArray) -> bool:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    YELLOW_STAR_RANGE_HSV = (np.array([51//2, 255,  255]), np.array([52//2, 255, 255]))
    pixels_yellow_star = np.count_nonzero(cv2.inRange(hsv, YELLOW_STAR_RANGE_HSV[0], YELLOW_STAR_RANGE_HSV[1]))
    return pixels_yellow_star > 0


def detect_ethereal(bgr: NDArray) -> bool:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    HOURGLASS_HSV_RANGE = (np.array([int(48//2), int(0.3*255), int(0.2 * 255)]), np.array([50//2, int(0.45*255), int(0.45 * 255)]))
    pixels_hourglass = np.count_nonzero(cv2.inRange(hsv, HOURGLASS_HSV_RANGE[0], HOURGLASS_HSV_RANGE[1]))
    return pixels_hourglass > 0


def detect_spell_gem_color(bgr: NDArray) -> SpellGemClass:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    DEATH_GEM_COLOR_HSV_RANGE = (np.array([240 // 2, int(0.20 * 255), int(0.4 * 255)]), np.array([240 // 2, int(0.3 * 255), int(0.9 * 255)]))
    SORCERY_GEM_COLOR_H_RANGE = (290 // 2, 310 // 2)
    LIFE_GEM_COLOR_HSV_RANGE = (np.array([int(15//2), int(0.5*255), int(0.4 * 255)]), np.array([50//2, int(0.91*255), int(0.85 * 255)]))
    CHAOS_GEM_COLOR_HSV_RANGE = (np.array([0, 255, int(0.1 * 255)]), np.array([0, 255, int(0.3 * 255)]))
    NATURE_GEM_COLOR_H_RANGE = (140 // 2, 150 // 2)

    h, s, v = cv2.split(hsv)
    death_mask = cv2.inRange(hsv, DEATH_GEM_COLOR_HSV_RANGE[0], DEATH_GEM_COLOR_HSV_RANGE[1])
    pixels_death = np.count_nonzero(death_mask)
    pixels_sorcery = np.count_nonzero(cv2.inRange(h, SORCERY_GEM_COLOR_H_RANGE[0], SORCERY_GEM_COLOR_H_RANGE[1]))
    pixels_life = np.count_nonzero(cv2.inRange(hsv, LIFE_GEM_COLOR_HSV_RANGE[0], LIFE_GEM_COLOR_HSV_RANGE[1]))
    pixels_chaos = np.count_nonzero(cv2.inRange(hsv, CHAOS_GEM_COLOR_HSV_RANGE[0], CHAOS_GEM_COLOR_HSV_RANGE[1]))
    pixels_nature = np.count_nonzero(cv2.inRange(h, NATURE_GEM_COLOR_H_RANGE[0], NATURE_GEM_COLOR_H_RANGE[1]))

    if pixels_chaos > 0:
        return SpellGemClass.CHAOS
    elif pixels_death > 0:
        return SpellGemClass.DEATH
    elif pixels_life > 0:
        return SpellGemClass.LIFE
    elif pixels_nature > 0:
        return SpellGemClass.NATURE
    elif pixels_sorcery > 0:
        return SpellGemClass.SORCERY
    else:
        raise NoSpellException("no class for spell gem")

@dataclass
class SpellEnchantDescription:
    spell_name: str
    tier_text: str
    charges: str
    description: str


def spell_enchant_description(spell_description_roi_bgr: NDArray, ocr_engine: OCR) -> str:
    text_result = ocr_engine.recognize_cv2_image(spell_description_roi_bgr)
    if not text_result.lines:
        return ""
    try:
        lines = text_result.lines
        spell_name = lines[0].merged_text
        tier = lines[1].merged_text
        charges = lines[2].merged_text.replace(" 1 ", " out of ")
        description = ' '.join(line.merged_text for line in lines[3:])
        return f"{spell_name}\n{tier}\n{charges}\n{description}"
    except IndexError:
        return ' '.join(line.merged_text for line in text_result.lines)


def spell_gem_description(spell_description_roi_bgr: NDArray, ocr_engine: OCR) -> str:
    text_result = ocr_engine.recognize_cv2_image(spell_description_roi_bgr)
    if not text_result.lines:
        return ""
    try:
        lines = text_result.lines
        spell_name = lines[0].merged_text
        charges = lines[1].merged_text.replace(" 1 ", " out of ")
        description = ' '.join(line.merged_text for line in lines[2:])
        return f"\n{charges}\n{description}\n{spell_name}"
    except IndexError:
        return ' '.join(line.merged_text for line in text_result.lines)


class NoSpellException(Exception):
    pass

def find_spell_gem_info(spell_name_roi: NDArray, ocr_engine: OCR) -> Optional[SpellSelectionInfo]:
    mask = detect_green_text(spell_name_roi)

    idxs = np.argwhere(mask == 255)
    try:
        top_left = idxs[0]
        bottom_right = idxs[-1]
    except IndexError:
        print("WARNING: unable to detect spell gem text selection")
        return

    text_results = ocr_engine.recognize_cv2_image(mask)
    selected_spell = text_results.merged_text
    if not text_results.lines:
        return

    top_left_x_percent = top_left[1] / spell_name_roi.shape[1]
    spell_gem_roi = slice_img(spell_name_roi, x_start=0.01, x_end=top_left_x_percent - 0.005,
                              y_start=top_left[0] / spell_name_roi.shape[0],
                              y_end=bottom_right[0] / spell_name_roi.shape[0])

    gold_star_roi = slice_img(spell_name_roi, x_start=0.01, x_end=1,
                              y_start=top_left[0] / spell_name_roi.shape[0],
                              y_end=bottom_right[0] / spell_name_roi.shape[0])
    detected_gem = detect_spell_gem_color(spell_gem_roi)
    is_ethereal = detect_ethereal(spell_gem_roi)
    has_yellow_star = detect_yellow_star(gold_star_roi)
    has_exclamation = detect_exclamation(gold_star_roi)
    if detected_gem:
        return SpellSelectionInfo(spell_name=selected_spell, gem_class=detected_gem, is_ethereal=is_ethereal, has_yellow_star=has_yellow_star, has_exclamation=has_exclamation)
    else:
        print(f"no gem found for spell gem {selected_spell}")


class ComponentSortUI:
    def __init__(self, ocr_engine: OCR):
        self.ocr_engine = ocr_engine
        self._prev_sort_text = ""
        self._sort_text = ""

    def ocr(self, sort_text_roi_bgr: NDArray):
        sort_text = self.ocr_engine.recognize_cv2_image(sort_text_roi_bgr)
        self._prev_sort_text = self._sort_text
        self._sort_text = sort_text.merged_text

    @property
    def text(self) -> str:
        return self._sort_text

    @property
    def is_same_state(self) -> bool:
        return self._prev_sort_text == self._sort_text

    @property
    def new_text(self) -> str:
        if self.is_same_state:
            return ""
        else:
            return self.text


class ComponentSpellDescription:
    def __init__(self, ocr_engine: OCR):
        self.ocr_engine = ocr_engine
        self._description = ""

    def ocr(self, roi: NDArray):
        self._description = spell_gem_description(roi, self.ocr_engine)

    @property
    def description(self):
        return self._description


class ComponentSpellProperties:
    def __init__(self, ocr_engine: OCR):
        self.ocr_engine = ocr_engine
        self._properties: Optional[OCRResult] = None
        self.prev_number_of_properties: int = 0
        self.number_of_properties: int = 0
        self.empty_slots: int = 3

    @property
    def text(self) -> str:
        if not self._properties:
            return ""

        return '\n'.join(line.merged_text for line in self._properties.lines)

    def ocr(self, roi: NDArray):
        self._properties = self.ocr_engine.recognize_cv2_image(detect_white_text(roi))
        self.prev_number_of_properties = self.number_of_properties
        self.number_of_properties = 0
        if not self._properties.lines:
            return

        if not self._properties.lines[0].merged_text.startswith("Properties"):
            return

        num_properties = 0
        self.empty_slots = 0
        for line in self._properties.lines[1:]:
            if "Empty Property Slot" in line.merged_text:
                self.empty_slots += 1
                continue
            if line.merged_text == "none":
                continue
            num_properties += 1
        self.number_of_properties = num_properties

    @property
    def is_same_state(self) -> bool:
        return self.number_of_properties == self.prev_number_of_properties

    @property
    def has_enchantment_slot(self) -> bool:
        return self.empty_slots > 0


def enchantment_property_number_text(cls: ComponentSpellProperties) -> str:
    if not cls.has_enchantment_slot:
        return "no enchantment slots left"

    if cls.is_same_state:
        return ""

    if cls.number_of_properties > 0:
        prop_count = cls.number_of_properties
        ending = "property" if prop_count == 1 else "properties"
        return f"{cls.number_of_properties} {ending}"
    else:
        return ""


def enchantment_empty_slots_text(cls: ComponentSpellProperties) -> str:
    if not cls.has_enchantment_slot:
        return "no enchantment slots left"

    if cls.is_same_state:
        return ""

    if cls.empty_slots > 0:
        empty_slot_count = cls.empty_slots
        ending = "slot" if empty_slot_count == 1 else "slots"
        return f"{cls.empty_slots} empty {ending}"
    else:
        return ""


class ComponentSpellEnchanterDescription:
    def __init__(self, ocr_engine: OCR):
        self.ocr_engine = ocr_engine
        self._description = ""

    def ocr(self, roi: NDArray):
        self._description = spell_enchant_description(roi, self.ocr_engine)

    @property
    def description(self):
        return self._description


class ComponentSpellInfo:
    """The spell's name, class,and whether it is ethereal"""
    def __init__(self, ocr_engine: OCR):
        self.ocr_engine = ocr_engine
        self._spell_gem_info: Optional[SpellSelectionInfo] = None
        self._prev_spell_gem_info: Optional[SpellSelectionInfo] = None

    def ocr(self, roi: NDArray):
        self._prev_spell_gem_info = self._spell_gem_info
        self._spell_gem_info = find_spell_gem_info(roi, self.ocr_engine)
        if self._spell_gem_info is None:
            self._spell_gem_info = SpellSelectionInfo(spell_name="unknown spell", gem_class=SpellGemClass.UNKNOWN)
            # raise Exception("unable to detect spell gem info")

    @property
    def is_same_state(self) -> bool:
        return self._spell_gem_info == self._prev_spell_gem_info

    @property
    def is_ethereal(self) -> bool:
        return self._spell_gem_info.is_ethereal

    @property
    def spell_name(self) -> str:
        return self._spell_gem_info.spell_name

    @property
    def spell_class(self) -> SpellGemClass:
        return self._spell_gem_info.gem_class

    @property
    def has_yellow_star(self) -> bool:
        return self._spell_gem_info.has_yellow_star

    @property
    def is_new_spell(self) -> bool:
        return self._spell_gem_info.has_exclamation


class ComponentDialogBox:
    """Dialog box text"""
    def __init__(self, ocr_engine: OCR):
        self.ocr_engine = ocr_engine
        self.dialog_text: str = ""
        self.prev_dialog_text: str = ""

    def ocr(self, roi: NDArray):
        self.prev_dialog_text = self.dialog_text
        if dialog_text := detect_dialog_text_color(roi, self.ocr_engine):
            self.dialog_text = dialog_text
        else:
            self.dialog_text = ""

    @property
    def is_same_state(self) -> bool:
        return self.dialog_text == self.prev_dialog_text


