import pprint
from dataclasses import dataclass
from importlib import resources

from subot.settings import Config
from subot.ui_areas.PerkScreen import PerkScreen
import cv2
from numpy.typing import NDArray
from subot.ocr import OCR


class AudioSystemTest:
    def __init__(self):
        self.texts: list[str] = []
        self.silence_count: int = 0

    def speak_nonblocking(self, text: str):
        self.texts.append(text)

    def speak_blocking(self, text: str):
        self.texts.append(text)

    def silence(self):
        self.silence_count += 1


@dataclass
class FrameHolderTest:
    frame: NDArray
    gray_frame: NDArray


def test_perk_ui():
    test_audio_system = AudioSystemTest()
    with resources.path(__package__, 'perk_screen_1280.png') as perk_path:
        img_color = cv2.imread(perk_path.as_posix(), cv2.IMREAD_UNCHANGED)
    img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGRA2GRAY)
    frame_holder = FrameHolderTest(img_color, img_gray)
    ocr_engine = OCR()
    config = Config()

    perk_ocr_system = PerkScreen(audio_system=test_audio_system, config=config, ocr_engine=ocr_engine)

    perk_ocr_system.ocr(frame_holder)
    perk_ocr_system.speak_auto()
    expected_perk_name = "Impiety (MAX)"
    assert perk_ocr_system.auto_text.startswith(expected_perk_name)
    perk_ocr_system.speak_interaction()
    assert perk_ocr_system.unspent_perk_points_text == "Unspent Perk Points: 94"

