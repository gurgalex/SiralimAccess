from importlib import resources
from pathlib import Path

from subot.settings import Config
from subot.ui_areas.FieldItemSelect import FieldItemSelectUI
import cv2
from subot.ocr import OCR
from tests.ui_screens.utils import AudioSystemTest, FrameHolderTest


def parse_test_frame_auto(img_path: Path, system):
    img_color = cv2.imread(img_path.as_posix(), cv2.IMREAD_UNCHANGED)
    img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGRA2GRAY)
    frame_holder = FrameHolderTest(img_color, img_gray)

    system.ocr(frame_holder)
    system.speak_auto()


def test_field_items_ui():
    test_audio_system = AudioSystemTest()
    ocr_engine = OCR()
    config = Config()
    inspect_screen_ui = FieldItemSelectUI(audio_system=test_audio_system, config=config, ocr_engine=ocr_engine)

    with resources.path(__package__, 'field_items_select_field_item.png') as test_img_path:
        parse_test_frame_auto(test_img_path, inspect_screen_ui)
        expected = "Scroll of Attack"
        assert test_audio_system.texts[-1].startswith(expected)

    with resources.path(__package__, 'field_items_use_it.png') as test_img_path:
        parse_test_frame_auto(test_img_path, inspect_screen_ui)
        expected = "Use it"
        assert test_audio_system.texts[-1].startswith(expected)

    with resources.path(__package__, 'field_items_creature_select.png') as test_img_path:
        parse_test_frame_auto(test_img_path, inspect_screen_ui)
        expected = "Apply to 1"
        assert test_audio_system.texts[-1].startswith(expected)

    with resources.path(__package__, 'field_items_dialog.png') as test_img_path:
        parse_test_frame_auto(test_img_path, inspect_screen_ui)
        expected = "You cannot use this item outside of your castle"
        assert test_audio_system.texts[-1].startswith(expected)



