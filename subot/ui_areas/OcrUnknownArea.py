import math
import time
from typing import Optional

import cv2
from numpy.typing import NDArray

from subot.models import Quest, QuestType, ChestSprite, ResourceNodeSprite, NPCSprite
from subot.ocr import OCR, detect_dialog_text, detect_green_text, OCRResult
from subot.settings import Config, Session
from subot.ui_areas.CodexGeneric import detect_any_text
from subot.ui_areas.base import SpeakAuto, FrameInfo, OCRMode, SpeakCapability
import numpy as np

import logging

root = logging.getLogger()


class OcrUnknownArea(SpeakAuto):
    mode = OCRMode.UNKNOWN
    QUEST_SCANNING_INTERVAL: float = 1.0
    RESIZE_FACTOR: int = 2

    def __init__(self, audio_system: SpeakCapability, config: Config, ocr_engine: OCR):
        super().__init__(ocr_engine, config, audio_system)
        self.previous_dialog_text: str = ""
        self.current_dialog_text: str = ""
        self.previous_selected_text: str = ""
        self.current_selected_text: str = ""
        self.current_selected_text_result: Optional[OCRResult] = None
        self.quest_sprite_long_names: set[str] = set()
        self.current_quests: list[Quest] = []
        self.current_quest_ids: set[int] = set()
        self.quest_text: str = ""
        self.menu_entry_text_repeat = False
        self.last_quest_scan: Optional[float] = None
        self.silenced: bool = True

    def ocr(self, parent: FrameInfo):
        if not self.last_quest_scan or (time.time() - self.last_quest_scan) >= OcrUnknownArea.QUEST_SCANNING_INTERVAL:
            t1 = time.time()
            quests = self.extract_quest_name_from_quest_area(parent.gray_frame)
            current_quests = [quest.title for quest in quests]
            quest_items = [sprite.long_name for quest in quests for sprite in quest.sprites]
            root.debug(f"quests = {current_quests}")
            root.debug(f"quest items = {quest_items}")

            self.update_quests(quests)
            t2 = time.time()
            total = t2 - t1
            root.debug(f"quest scanning took {math.ceil(total * 1000)}ms")
            self.last_quest_scan = time.time()

        if not self.program_config.ocr_enabled:
            return
        self.ocr_dialog_box(parent.frame, parent.gray_frame)
        self.ocr_selected_menu_item(parent.frame)

    def _should_speak_dialog(self) -> bool:
        if not self.current_dialog_text:
            return False
        if self.previous_dialog_text == self.current_dialog_text:
            return False

        return True

    def _should_speak_menu_selection(self) -> bool:
        if not self.current_selected_text:
            return False
        if self.previous_selected_text == self.current_selected_text:
            return False
        return True

    def speak_auto(self):
        if self._should_speak_dialog():
            root.debug(f"Speaking dialog text: {self.current_dialog_text}")
            self.audio_system.speak_nonblocking(self.current_dialog_text)
            self.silenced = False
        if self._should_speak_menu_selection():
            help_text = self.gen_help_text()
            text = f"{self.current_selected_text} {help_text}"
            root.debug(f"{self.current_dialog_text=}")
            self.audio_system.speak_nonblocking(text)
            self.silenced = False

        no_dialog_box_or_menu = not self.current_dialog_text and not self.current_selected_text
        if no_dialog_box_or_menu and not self.silenced:
            self.current_selected_text = ""
            self.current_dialog_text = ""
            self.audio_system.silence()
            self.silenced = True

    def force_ocr_content(self, gray_frame: NDArray):
        """Force OCR of side content right of green menu select text"""
        if not self.current_selected_text_result:
            return

        last_word_rect = self.current_selected_text_result.lines[0].words[-1].bounding_rect
        last_word_rect_end_x_pos: int = (last_word_rect.x + last_word_rect.width) * self.RESIZE_FACTOR
        x_start = last_word_rect_end_x_pos / gray_frame.shape[1] / self.RESIZE_FACTOR
        if x_start >= 1:
            return
        forced_side_result = detect_any_text(gray_frame, self.ocr_engine, x_start=x_start, x_end=1.00, y_start=0.00, y_end=1.0)
        self.audio_system.speak_nonblocking(forced_side_result.merged_text)

    def get_quest_items(self) -> set[str]:
        return self.quest_sprite_long_names

    def speak_interaction(self) -> str:
        """Text spoken with from user interaction"""
        if self.current_dialog_text:
            text = self.current_dialog_text
            self.audio_system.speak_nonblocking(text)
            return text
        if self.quest_text:
            text = self.quest_text
            self.audio_system.speak_nonblocking(text)
            return text

    def update_quests(self, new_quests: list[Quest]):
        self.current_quests = new_quests
        if len(new_quests) == 0:
            return

        new_quest_ids = set()
        for quest in new_quests:
            new_quest_ids.add(quest.id)

        if new_quest_ids == self.current_quest_ids:
            return

        root.debug(f"{self.quest_text=}")
        if self.quest_text:
            if self.program_config.ocr_enabled:
                self.audio_system.speak_nonblocking(self.quest_text)

        self.quest_sprite_long_names.clear()
        with Session() as session:
            for quest in new_quests:
                if quest.quest_type == QuestType.rescue:
                    self.quest_sprite_long_names = set(
                        sprite.long_name for sprite in session.query(NPCSprite).all())
                elif quest.quest_type == QuestType.resource_node:
                    self.quest_sprite_long_names = set(
                        sprite.long_name for sprite in session.query(ResourceNodeSprite).all())
                elif quest.quest_type == QuestType.cursed_chest:
                    self.quest_sprite_long_names = set(sprite.long_name for sprite in
                                                       session.query(ChestSprite).filter(
                                                           ChestSprite.realm_id.is_not(None)).all())
                else:
                    for sprite in quest.sprites:
                        self.quest_sprite_long_names.add(sprite.long_name)

                if not quest.supported:
                    self.audio_system.speak_nonblocking(f"Unsupported quest: {quest.title} {quest.description}")

        self.current_quest_ids = new_quest_ids

    def ocr_dialog_box(self, frame: NDArray, gray_frame: NDArray):
        self.previous_dialog_text = self.current_dialog_text
        self.current_dialog_text = ""
        dialog_result = detect_dialog_text(frame, gray_frame, self.ocr_engine)

        # don't count no text at all as dialog text
        if not dialog_result:
            return
        self.current_dialog_text = dialog_result

        root.debug(f"dialog box text = '{dialog_result}'")

    def ocr_selected_menu_item(self, frame: NDArray):
        self.previous_selected_text = self.current_selected_text
        self.current_selected_text = ""
        mask = detect_green_text(frame)
        # remove non-font green pixels
        start_blur_time = time.time()
        blurred = cv2.medianBlur(mask, 3)
        end_blur_time = time.time()
        root.debug(f"blurring took {math.ceil((end_blur_time - start_blur_time) * 1000)}ms")
        x, y, w, h = cv2.boundingRect(blurred)

        no_match = w == 0 or h == 0
        if no_match:
            return

        # padding around font is used to improve OCR output
        padding = 16

        # don't go out of bounds
        y_start = max(y - padding, 0)
        y_end = min(y + h + padding, mask.shape[0])
        x_start = max(x - padding, 0)
        x_end = min(x + w + padding, mask.shape[1])

        roi = mask[y_start:y_end, x_start:x_end]
        # only resize if image capture area likely contains a single section of text (saves CPU)
        if roi.shape[0] < 400 or roi.shape[1] < 400:
            roi = cv2.resize(roi, (roi.shape[1] * self.RESIZE_FACTOR, roi.shape[0] * self.RESIZE_FACTOR), interpolation=cv2.INTER_LINEAR)

        ocr_result = self.ocr_engine.recognize_cv2_image(roi)
        selected_text = ocr_result.merged_text
        self.menu_entry_text_repeat = False

        # don't repeat announcing the same or no text at all
        if selected_text == "":
            return
        elif selected_text == self.current_selected_text:
            self.menu_entry_text_repeat = True

        self.current_selected_text_result = ocr_result
        self.current_selected_text = selected_text

    def extract_quest_name_from_quest_area(self, gray_frame: np.typing.ArrayLike) -> list[Quest]:
        """

        :param gray_frame: greyscale full-windowed frame that the bot captured
        :return: List of quests that appeared in the quest area. an empty list is returned if no quests were found
        """
        quests: list[Quest] = []
        y_text_dim = int(gray_frame.shape[0] * 0.33)
        x_text_dim = int(gray_frame.shape[1] * 0.30)
        quest_area = gray_frame[:y_text_dim, -x_text_dim:]
        thresh, threshold_white = cv2.threshold(quest_area, 215, 255, cv2.THRESH_BINARY_INV)

        text = self.ocr_engine.recognize_cv2_image(threshold_white)

        self.quest_text = text.merged_text
        # see if any lines match a quest title
        with Session() as session:
            for line_info in text.lines:
                line_text = line_info.merged_text.strip()
                quest_obj: Quest
                # fast check - no changes
                if quest_res := session.query(Quest.id).filter_by(title_first_line=line_text).first():
                    (quest_id,) = quest_res
                    if quest_id in self.current_quest_ids:
                        # return existing quests since no change
                        return self.current_quests
                if quest_obj := session.query(Quest).filter_by(title_first_line=line_text).first():
                    quests.append(quest_obj)
        return quests

    def gen_help_text(self) -> str:
        if self.current_dialog_text:
            return f"\npress {self.program_config.read_secondary_key} to here dialog box"
        else:
            return ""
