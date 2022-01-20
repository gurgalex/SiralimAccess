from importlib import resources
import pytest
from subot.ocr import OCR
from subot.settings import Config
from subot.ui_areas.enchanter.upgrade import SpellUpgradeUI
from tests.ui_screens.utils import ocr_test_frame


@pytest.fixture
def enchant_upgrade_ui(audio_system_test):
    ocr_engine = OCR()
    config = Config()

    return SpellUpgradeUI(audio_system=audio_system_test, config=config, ocr_engine=ocr_engine)


def test_spell_information(audio_system_test, enchant_upgrade_ui):
    with resources.path(__package__, 'upgrade_equipped_full_rank_life.png') as path:
        ocr_test_frame(path, enchant_upgrade_ui)
    enchant_upgrade_ui.speak_auto()
    assert "LIFE class" in audio_system_test.last_text


def test_tier_spoken_in_description(audio_system_test, enchant_upgrade_ui):
    with resources.path(__package__, 'upgrade_equipped_full_rank_life.png') as path:
        ocr_test_frame(path, enchant_upgrade_ui)

    enchant_upgrade_ui.speak_interaction()
    assert audio_system_test.last_text.startswith("Cosmic Ripple (Squash)\nTier: 15")
    assert "Target takes a moderate amount of damage" in audio_system_test.last_text