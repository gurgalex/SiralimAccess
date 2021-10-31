import copy
from typing import Optional

import cv2

from subot.ocr import detect_green_text, detect_white_text, OCR
from subot.audio import AudioSystem
from subot.settings import Config
from subot.trait_info import Creature, CreatureInfo, TraitData, CreatureLimited
import numpy as np
import pyclip as clip
from logging import getLogger
root = getLogger()


class OcrSummoningSystem:
    """System active when summoning screen is open
    Discarded when closed

    """
    def __init__(self, creature_data: TraitData, audio_system: AudioSystem, config: Config, ocr_engine: OCR):

        self.prev_creature: Optional[CreatureInfo] = None
        self.creature: Optional[CreatureInfo] = None
        self.creature_data = creature_data
        self.audio_system: AudioSystem = audio_system
        self.program_config = config
        self.ocr_engine = ocr_engine

    def ocr(self, frame: np.typing.ArrayLike, gray_frame: np.typing.ArrayLike):
        self._ocr_summoning(frame, gray_frame)

    def speak_auto(self) -> Optional[str]:
        """Text spoken without any user interaction"""
        if not self.creature:
            return
        text = self.creature.name
        hint_text = f".\nPress {self.program_config.read_secondary_key} to hear trait and trait description. Press {'v'} to hear all available info, press {'c'} to copy all available info to clipboard"
        if self.creature != self.prev_creature:
            combined_text = f"{text} {hint_text}"
            self.audio_system.speak_nonblocking(combined_text)
        return text

    def speak_interaction(self) -> str:
        """Speaks text which requires a summary key press"""
        text = f"trait: {self.creature.trait}\n Description: {self.creature.trait_description}"
        self.audio_system.speak_nonblocking(text)
        return text

    def detailed_text(self) -> str:
        if isinstance(self.creature, Creature):
            return f"""Creature
name: {self.creature.name}
race: {self.creature.race}
class: {self.creature.klass}
trait material: {self.creature.trait_material}
sources: {self.creature.sources}
health: {self.creature.health}
attack: {self.creature.attack}
intelligence: {self.creature.intelligence}
defense: {self.creature.defense}
speed: {self.creature.speed}
trait: {self.creature.trait}
trait description: {self.creature.trait_description}
"""
        elif isinstance(self.creature, CreatureLimited):
            return f"""Creature
name: {self.creature.name}
trait: {self.creature.trait}
trait description: {self.creature.trait_description}
"""
        else:
            return "no creature info available"

    def speak_detailed(self):
        text = self.detailed_text()
        self.audio_system.speak_nonblocking(text)
        return text

    def copy_detailed_text(self):
        text = self.detailed_text()
        clip.copy(text)
        if not self.creature:
            return
        copy_msg = f"copied {self.creature.name} creature info to clipboard"
        self.audio_system.speak_nonblocking(copy_msg)

    def _manual_ocr(self, frame, gray_frame, creature_name: str) -> Optional[CreatureInfo]:
        mask_trait_name = detect_white_text(frame, x_start=0.5, x_end=1.0, y_start=0.5, y_end=0.6)
        trait_name_results = self.ocr_engine.recognize_cv2_image(mask_trait_name)
        trait_name = None
        try:
            trait_name = trait_name_results.lines[0]["merged_text"].lower()
            creature = self.creature_data.by_trait_name(trait_name)
            root.debug(f"identified creature by trait: {creature.name}")
            return creature
        except KeyError:
            pass
        except IndexError:
            print("no trait name found")

        # fallback to ocr
        y_start = int(gray_frame.shape[0] * 0.50)
        y_end = int(gray_frame.shape[0] * 0.9)
        x_start = int(gray_frame.shape[1] * 0.45)
        x_end = int(gray_frame.shape[1] * 1)

        trait_and_text_area = gray_frame[y_start:y_end, x_start:x_end]

        resize_factor = 2
        trait_mask_resized = cv2.resize(trait_and_text_area, (trait_and_text_area.shape[1] * resize_factor, trait_and_text_area.shape[0] * resize_factor),
                                        interpolation=cv2.INTER_LINEAR)
        ocr_trait_area_results = self.ocr_engine.recognize_cv2_image(trait_mask_resized)
        if ocr_trait_area_results.merged_text:
            try:
                lines = ocr_trait_area_results.lines

                root.debug(ocr_trait_area_results.merged_text)
                trait_desc = ' '.join(line["merged_text"] for line in lines[1:])
                return CreatureLimited(name=creature_name, trait=trait_name, trait_description=trait_desc)

            except IndexError:
                root.info("no trait info even with manual OCR")
                return None

    def _ocr_summoning(self, frame: np.typing.ArrayLike, gray_frame: np.typing.ArrayLike):
        creature_name_mask = detect_green_text(frame, y_start=0.0, y_end=1, x_start=0.05, x_end=0.4)
        ocr_result_creature_name = self.ocr_engine.recognize_cv2_image(creature_name_mask)
        creature_name = ocr_result_creature_name.merged_text
        self.prev_creature = copy.deepcopy(self.creature)
        self.creature = None

        try:
            creature = self.creature_data.by_creature_name(creature_name)
            self.creature = creature
            root.debug(f"identified creature by name: {self.creature.name}")
        except KeyError:
            pass

        if not self.creature:
            self.creature = self._manual_ocr(frame, gray_frame, creature_name)

        if self.creature is None:
            root.info(f"no data for creature: {creature_name}")
