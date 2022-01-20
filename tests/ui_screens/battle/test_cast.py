from importlib import resources
import pytest
from subot.ocr import OCR
from subot.settings import Config
from subot.ui_areas.battle.cast import BattleCastUI
from tests.ui_screens.utils import ocr_test_frame


@pytest.fixture
def battle_cast_ui(audio_system_test) -> BattleCastUI:
    ocr_engine = OCR()
    config = Config()

    return BattleCastUI(audio_system=audio_system_test, config=config, ocr_engine=ocr_engine)


def test_non_ethereal_spell(audio_system_test, battle_cast_ui):
    with resources.path(__package__, 'battle_cast_affliction_life.png') as path:
        ocr_test_frame(path, battle_cast_ui)
    battle_cast_ui.speak_auto()
    assert "LIFE class" in audio_system_test.last_text
    assert "Affliction" in audio_system_test.last_text
    assert "ethereal" not in audio_system_test.last_text

    # spell description and properties
    battle_cast_ui.speak_interaction()
    assert audio_system_test.last_text.startswith("Charges: 7 out of 7")


def test_test_ethereal_spell(audio_system_test, battle_cast_ui):
    with resources.path(__package__, 'nature-ethereal.png') as path:
        ocr_test_frame(path, battle_cast_ui)
    battle_cast_ui.speak_auto()
    assert "NATURE class" in audio_system_test.last_text
    assert "Morph: Nature" in audio_system_test.last_text
    assert "ethereal" in audio_system_test.last_text
