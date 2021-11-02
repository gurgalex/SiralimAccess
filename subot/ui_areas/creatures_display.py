from typing import Optional
from subot.ocr import detect_green_text, detect_white_text, OCR, detect_dialog_text
from subot.audio import AudioSystem
from subot.settings import Config
from subot.trait_info import Creature, CreatureInfo, TraitData, CreatureLimited
import numpy as np
import pyclip as clip
from logging import getLogger

from subot.ui_areas.base import SpeakAuto
from subot.ui_areas.shared import detect_creature_party_selection

root = getLogger()


class OCRCreaturesDisplaySystem(SpeakAuto):
    """System active when the 6 creature display is open
    Discarded when closed

    """
    def __init__(self, creature_data: TraitData, audio_system: AudioSystem, config: Config, ocr_engine: OCR):

        self.prev_menu_text: Optional[str] = None
        self.menu_text: Optional[str] = None
        self.audio_system: AudioSystem = audio_system
        self.program_config = config
        self.creature_position: Optional[int] = None
        self.prev_creature_position: Optional[int] = None
        self.ocr_engine = ocr_engine
        self.current_dialog_text: str = ""
        self.previous_dialog_text: str = ""

    def help_text(self) -> str:
        return ""
        # todo: help text for each menu option if additional text info
        if self.menu_text == "Creature Sheet":
            return f".\nPress {self.program_config.read_secondary_key} to hear creature name. Press {self.program_config.read_all_info_key} to hear all available info, press {self.program_config.copy_all_info_key} to copy all available info to clipboard"
        return ""

    def ocr(self, frame: np.typing.ArrayLike, gray_frame: np.typing.ArrayLike):
        self._ocr_creature(frame, gray_frame)
        self.previous_dialog_text = self.current_dialog_text
        self.current_dialog_text = detect_dialog_text(frame, gray_frame, self.ocr_engine)

    def creature_text(self) -> str:
        menu_item = self.menu_text
        hint_text = self.help_text()
        if self.creature_position is None:
            return ""
        if self.creature_position != self.prev_creature_position:
            return f"Creature {self.creature_position} {menu_item} {hint_text}"
        if self.menu_text != self.prev_menu_text:
            return f"{menu_item} {hint_text}"
        else:
            return ""

    def _should_speak_dialog(self) -> bool:
        if not self.current_dialog_text:
            return False
        if self.current_dialog_text == self.previous_dialog_text:
            return False
        return True

    def speak_auto(self) -> Optional[str]:
        """Text spoken without any user interaction"""
        if self._should_speak_dialog():
            text = self.current_dialog_text
            self.audio_system.speak_nonblocking(text)
            return text
        if not self.menu_text:
            return
        text = self.creature_text()
        if text:
            self.audio_system.speak_nonblocking(text)
        return text

    def speak_interaction(self) -> str:
        """Speaks text which requires a summary key press"""
        return ""

    def detailed_text(self) -> str:
        return ""

    def speak_detailed(self):
        text = self.detailed_text()
        self.audio_system.speak_nonblocking(text)
        return text

    def copy_detailed_text(self):
        text = self.detailed_text()
        clip.copy(text)
        if not self.menu_text:
            return
        copy_msg = f"copied {self.menu_text} creature info to clipboard"
        self.audio_system.speak_nonblocking(copy_msg)

    def _manual_ocr(self, frame, gray_frame, creature_name: str) -> Optional[CreatureInfo]:
        return

    def _ocr_creature(self, frame: np.typing.ArrayLike, gray_frame: np.typing.ArrayLike):
        selected_menu_mask = detect_green_text(frame, y_start=0.0, y_end=0.70, x_start=0.05, x_end=0.4)
        selected_menu_item = self.ocr_engine.recognize_cv2_image(selected_menu_mask)
        self.prev_menu_text = self.menu_text
        self.menu_text = None

        try:
            first_selected_text = selected_menu_item.lines[0].merged_text
            if first_selected_text:
                self.menu_text = first_selected_text
        except IndexError:
            print("no menu item selected")
            self.menu_text = None

        self.prev_creature_position = self.creature_position
        self.creature_position = detect_creature_party_selection(frame)

        if self.menu_text == "Creature Sheet":
            creature_sheet_mask = detect_white_text(frame, y_start=0.0, y_end=0.70, x_start=0.33, x_end=1.0, resize_factor=2, sensitivity=125)

            creature_sheet = self.ocr_engine.recognize_cv2_image(creature_sheet_mask)
            for line in creature_sheet.lines:
                pass
