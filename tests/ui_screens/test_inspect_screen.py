from importlib import resources

from subot.settings import Config
from subot.ui_areas.InspectScreenUI import InspectScreenUI
import cv2
from subot.ocr import OCR
from tests.ui_screens.utils import AudioSystemTest, FrameHolderTest


def test_perk_ui():
    test_audio_system = AudioSystemTest()
    with resources.path(__package__, 'inspect_screen_pg1.png') as test_img_path:
        img_color = cv2.imread(test_img_path.as_posix(), cv2.IMREAD_UNCHANGED)
    img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGRA2GRAY)
    frame_holder = FrameHolderTest(img_color, img_gray)
    ocr_engine = OCR()
    config = Config()

    inspect_screen_ui = InspectScreenUI(audio_system=test_audio_system, config=config, ocr_engine=ocr_engine)

    inspect_screen_ui.ocr(frame_holder)
    inspect_screen_ui.speak_auto()
    expected_auto_text_start = "Bloody Eft"
    assert inspect_screen_ui.creature_name.startswith(expected_auto_text_start)

    assert inspect_screen_ui.creature_class == "Nature"
    assert inspect_screen_ui.creature_race.endswith("Eft")
    assert inspect_screen_ui.creature_personality.startswith("Protective")

    inspect_screen_ui.speak_interaction()

    stat_lines = inspect_screen_ui.creature_stats.split("\n")

    assert stat_lines[0].endswith("Health 438.60M")
    assert stat_lines[1].endswith("Attack 110.63M")
    assert stat_lines[2].endswith("Intelligence 225.11M")
    assert stat_lines[3].endswith("Defense 685.56M")
    assert stat_lines[4].endswith("Speed 240.91M")

    assert inspect_screen_ui.right_text_first_line == "Pride of the Pack"

