from enum import Enum, auto

from numpy.typing import NDArray

from subot.ocr import OCR, detect_green_text, detect_white_text
from subot.settings import Config
from subot.ui_areas.base import SpeakAuto, FrameInfo, OCRMode, SpeakCapability


class SelectStep(Enum):
    DEPTH = auto()
    INSTABILITY = auto()
    REALM = auto()


class OCRRealmSelect(SpeakAuto):
    mode = OCRMode.REALM_SELECT

    def __init__(self, audio_system: SpeakCapability, config: Config, ocr_engine: OCR, step: SelectStep):
        super().__init__(ocr_engine, config, audio_system)
        self.help_text: str = ""
        self.step = step
        self.interactive_text: str = ""
        self.realm_info_text: str = ""

    def _realm_properties(self, frame: NDArray) -> str:
        mask = detect_white_text(frame, x_start=0.66, x_end=1.00, y_start=0.16, y_end=1.00)
        text = self.ocr_engine.recognize_cv2_image(mask)
        if not text.merged_text:
            return ""
        if text.lines[0].merged_text.lower() == "no properties":
            return "No properties"
        else:
            return text.merged_text

    def _depth_ocr(self, gray_frame: NDArray):
        self.prev_auto_text = self.auto_text
        x_start = int(gray_frame.shape[1] * 0.00)
        x_end = int(gray_frame.shape[1] * 0.33)
        y_start = int(gray_frame.shape[0] * 0.3)
        y_end = int(gray_frame.shape[0] * 0.57)

        depth_area = gray_frame[y_start:y_end, x_start:x_end]

        result = self.ocr_engine.recognize_cv2_image(depth_area)
        depth = result.lines[0].merged_text
        self.auto_text = f"Depth {depth}"
        self.interactive_text = ' '.join(line.merged_text for line in result.lines[1:])
        self.help_text = f"Press {self.program_config.read_secondary_key} to read enemy level and and max realm depth. Press {self.program_config.read_all_info_key} to speak Realm Properties"

    def _realm_instability(self, gray_frame: NDArray):
        self.prev_auto_text = self.auto_text
        x_start = int(gray_frame.shape[1] * 0.00)
        x_end = int(gray_frame.shape[1] * 0.28)
        y_start = int(gray_frame.shape[0] * 0.56)
        y_end = int(gray_frame.shape[0] * 1.00)

        instability_area = gray_frame[y_start:y_end, x_start:x_end]
        result = self.ocr_engine.recognize_cv2_image(instability_area)
        instability_text = result.lines[3].merged_text
        self.auto_text = f"Instability {instability_text}"
        self.interactive_text = ""
        self.help_text = f"Press {self.program_config.read_all_info_key} to speak realm properties"

    def _realm_select(self, frame: NDArray):
        mask = detect_green_text(frame, x_start=0.36, x_end=0.66, y_start=0.10, y_end=1.00)
        result = self.ocr_engine.recognize_cv2_image(mask)
        self.prev_auto_text = self.auto_text
        realm_text = result.merged_text
        self.interactive_text = ""
        if realm_text.strip():
            self.auto_text = realm_text
        else:
            self.auto_text = "Unknown realm selection"
        self.help_text = f"Press {self.program_config.read_all_info_key} to speak realm properties"

    def ocr(self, parent: FrameInfo):
        self.realm_info_text = self._realm_properties(parent.frame)
        self.prev_auto_text = self.auto_text
        if self.step is SelectStep.DEPTH:
            self._depth_ocr(parent.gray_frame)
        elif self.step is SelectStep.INSTABILITY:
            self._realm_instability(parent.gray_frame)
        elif self.step is SelectStep.REALM:
            self._realm_select(parent.frame)

    def speak_interaction(self):
        text = self.interactive_text
        self.audio_system.speak_nonblocking(text)

    def speak_all_info(self):
        text = f"{self.realm_info_text}"
        self.audio_system.speak_nonblocking(text)