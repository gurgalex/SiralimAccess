from importlib import resources
import pytest
from subot.ocr import OCR
from subot.settings import Config
from subot.ui_areas.refinery.spell import SalvageSpellUI
from tests.ui_screens.utils import ocr_test_frame


@pytest.fixture
def salvage_spell_ui(audio_system_test) -> SalvageSpellUI:
    ocr_engine = OCR()
    config = Config()

    return SalvageSpellUI(audio_system=audio_system_test, config=config, ocr_engine=ocr_engine)


def test_spell_information(audio_system_test, salvage_spell_ui):
    with resources.path(__package__, 'grind_spell.png') as path:
        ocr_test_frame(path, salvage_spell_ui)
    salvage_spell_ui.speak_auto()
    assert "Death Blossom" in audio_system_test.last_text
    assert "NATURE class" in audio_system_test.last_text

    salvage_spell_ui.speak_interaction()
    assert "Enemies take a small amount of damage 3 times." in audio_system_test.last_text
    assert "24% More Charges" in audio_system_test.last_text
