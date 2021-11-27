from importlib import resources

from subot.settings import Config
from subot.ui_areas.AnointmentClaimUI import AnointmentClaimUI
import cv2
from subot.ocr import OCR
from tests.ui_screens.utils import AudioSystemTest, FrameHolderTest


def test_perk_ui():
    test_audio_system = AudioSystemTest()
    with resources.path(__package__, 'choose_an_anointment_to_claim_ui.png') as img_path:
        img_color = cv2.imread(img_path.as_posix(), cv2.IMREAD_UNCHANGED)
    img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGRA2GRAY)
    frame_holder = FrameHolderTest(img_color, img_gray)
    ocr_engine = OCR()
    config = Config()

    anointment_claim_ocr_system = AnointmentClaimUI(audio_system=test_audio_system, config=config, ocr_engine=ocr_engine)

    anointment_claim_ocr_system.ocr(frame_holder)
    anointment_claim_ocr_system.speak_auto()
    expected_auto_text = "Death Sentence"
    assert anointment_claim_ocr_system.auto_text.startswith(expected_auto_text)
    anointment_claim_ocr_system.speak_interaction()
    spoken_interaction_text = test_audio_system.texts[1]
    assert spoken_interaction_text == "Death Sentence Your creatures' critical attacks deal 60% more damage."
