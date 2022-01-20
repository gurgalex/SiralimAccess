
from importlib import resources
import pytest
from subot.ocr import OCR
from subot.settings import Config
from tests.ui_screens.utils import AudioSystemTest, ocr_test_frame

from subot.ui_areas.enchanter.spell_craft_screen import SpellCraftUI


@pytest.fixture
def enchant_craft_ui(audio_system_test):
    ocr_engine = OCR()
    config = Config()

    return SpellCraftUI(audio_system=audio_system_test, config=config, ocr_engine=ocr_engine)


def test_spell_information(audio_system_test, enchant_upgrade_ui):
    with resources.path(__package__, 'craft_sorcery_class.png') as path:
        ocr_test_frame(path, enchant_upgrade_ui)
    enchant_upgrade_ui.speak_auto()
    assert "SORCERY class" in audio_system_test.last_text

    enchant_upgrade_ui.speak_interaction()
    assert audio_system_test.last_text.startswith("Charges: 10 out of 10")
    assert "Target takes a small amount of damage" in audio_system_test.last_text
    assert audio_system_test.last_text.endswith("Shatter")


def test_sort_indicator(audio_system_test, enchant_upgrade_ui):
    with resources.path(__package__, 'craft_sort_by_name.png') as path:
        ocr_test_frame(path, enchant_upgrade_ui)
    enchant_upgrade_ui.speak_auto()

    assert audio_system_test.last_text.startswith("Acid Breath")
    assert "Sorting By: [Name]" in audio_system_test.last_text

    with resources.path(__package__, 'craft_sorcery_class.png') as path:
        ocr_test_frame(path, enchant_upgrade_ui)
    enchant_upgrade_ui.speak_auto()
    sort_order_only_read_once = "Sorting By: [Name]" not in audio_system_test.last_text
    assert sort_order_only_read_once

