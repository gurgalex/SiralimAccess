from importlib import resources
import pytest
from subot.ocr import OCR
from subot.settings import Config
from subot.ui_areas.equip_spell_gem import EquipSpellGemUI
from tests.ui_screens.utils import ocr_test_frame


@pytest.fixture
def equip_spell_gem_ui(audio_system_test) -> EquipSpellGemUI:
    ocr_engine = OCR()
    config = Config()

    return EquipSpellGemUI(audio_system=audio_system_test, config=config, ocr_engine=ocr_engine)


def test_basic_spell_info(audio_system_test, equip_spell_gem_ui):
    with resources.path(__package__, 'equip_spell_gem.png') as path:
        ocr_test_frame(path, equip_spell_gem_ui)
    equip_spell_gem_ui.speak_auto()
    assert "LIFE class" in audio_system_test.last_text
    assert "Absolute Corruption" in audio_system_test.last_text

    equip_spell_gem_ui.speak_interaction()
    assert "Target's buffs are converted to random debuffs" in audio_system_test.last_text
    assert "19% Chance to Cast After Healing" in audio_system_test.last_text


