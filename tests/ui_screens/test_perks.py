from importlib import resources

from subot.settings import Config
from subot.ui_areas.PerkScreen import PerkScreen
import cv2
from subot.ocr import OCR
from tests.ui_screens.utils import AudioSystemTest, FrameHolderTest


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

