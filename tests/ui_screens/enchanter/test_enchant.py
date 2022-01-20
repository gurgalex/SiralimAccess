from importlib import resources

import pytest

from subot.ui_areas.enchanter.enchant_screen import SpellEnchantUI
from tests.ui_screens.utils import ocr_test_frame

from subot.ui_areas.enchanter.disenchant import SpellDisenchantUI


@pytest.fixture
def spell_enchant_ui(audio_system_test, config, ocr_engine) -> SpellEnchantUI:

    return SpellEnchantUI(audio_system=audio_system_test, config=config, ocr_engine=ocr_engine)


def test_enchant_basic_info(audio_system_test, spell_enchant_ui):

    with resources.path(__package__, 'enchant_2_free_slots.png') as path:
        ocr_test_frame(path, spell_enchant_ui)
    spell_enchant_ui.speak_auto()

    assert audio_system_test.last_text.startswith("Ancient Prayer")
    assert "Equipped" in audio_system_test.last_text
    assert "2 empty slots" in audio_system_test.last_text


def test_zero_property_spell_gem(audio_system_test, spell_enchant_ui):

    # test no properties
    with resources.path(__package__, 'enchant_no_properties.png') as path:
        ocr_test_frame(path, spell_enchant_ui)
    spell_enchant_ui.speak_auto()
    assert "upgrade to enchant further" in audio_system_test.last_text


def test_notification_fully_enchanted(audio_system_test, spell_enchant_ui):
    with resources.path(__package__, 'enchant_fully_enchanted.png') as path:
        ocr_test_frame(path, spell_enchant_ui)
    spell_enchant_ui.speak_auto()
    assert "fully enchanted already" in audio_system_test.last_text
