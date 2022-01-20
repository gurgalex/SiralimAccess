from importlib import resources

import pytest

from tests.ui_screens.utils import ocr_test_frame

from subot.ui_areas.enchanter.disenchant import SpellDisenchantUI


@pytest.fixture
def spell_disenchant_ui(audio_system_test, config, ocr_engine) -> SpellDisenchantUI:

    return SpellDisenchantUI(audio_system=audio_system_test, config=config, ocr_engine=ocr_engine)


def test_disenchant_ui(audio_system_test, spell_disenchant_ui):

    with resources.path(__package__, 'disenchant_equipped_no_properties.png') as path:
        ocr_test_frame(path, spell_disenchant_ui)
    spell_disenchant_ui.speak_auto()

    assert audio_system_test.last_text.startswith("Ancient Prayer")
    assert "already fully disenchanted" in audio_system_test.last_text
    assert "Equipped" in audio_system_test.last_text


def test_zero_property_spell_gem(audio_system_test, spell_disenchant_ui):

    # test no properties
    with resources.path(__package__, 'disenchant_equipped_fully_disenchanted.png') as path:
        ocr_test_frame(path, spell_disenchant_ui)
    spell_disenchant_ui.speak_auto()
    assert "already fully disenchanted" in audio_system_test.last_text


def test_selected_slot(audio_system_test, spell_disenchant_ui):
    # test disenchant slot UI
    with resources.path(__package__, 'disenchant_slot.png') as path:
        ocr_test_frame(path, spell_disenchant_ui)
    spell_disenchant_ui.speak_auto()

    assert audio_system_test.last_text == "Generous"

    spell_disenchant_ui.speak_interaction()
    assert audio_system_test.last_text.startswith("Zephyr (Melon)")
