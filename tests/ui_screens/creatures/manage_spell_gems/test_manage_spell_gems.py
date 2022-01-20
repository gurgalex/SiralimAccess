from importlib import resources
import pytest
from subot.ocr import OCR
from subot.settings import Config
from subot.ui_areas.manage_spell_gems import ManageSpellGemsUI
from tests.ui_screens.utils import ocr_test_frame


@pytest.fixture
def manage_spell_gems_ui(audio_system_test) -> ManageSpellGemsUI:
    ocr_engine = OCR()
    config = Config()

    return ManageSpellGemsUI(audio_system=audio_system_test, config=config, ocr_engine=ocr_engine)


def test_empty_slot(audio_system_test, manage_spell_gems_ui):
    with resources.path(__package__, 'creature1_empty_slot.png') as path:
        ocr_test_frame(path, manage_spell_gems_ui)
    manage_spell_gems_ui.speak_auto()
    assert "Empty Slot" in audio_system_test.last_text


def test_basic_spell_info(audio_system_test, manage_spell_gems_ui):
    with resources.path(__package__, 'creature1_default_gem.png') as path:
        ocr_test_frame(path, manage_spell_gems_ui)
    manage_spell_gems_ui.speak_auto()
    assert "LIFE class" in audio_system_test.last_text
    assert "Death Blossom" in audio_system_test.last_text

    manage_spell_gems_ui.speak_interaction()
    assert "100% Chance to Cast Twice" in audio_system_test.last_text


def test_default_spell_gem_found(audio_system_test, manage_spell_gems_ui):
    with resources.path(__package__, 'creature1_default_gem.png') as path:
        ocr_test_frame(path, manage_spell_gems_ui)
    manage_spell_gems_ui.speak_auto()
    assert "default" in audio_system_test.last_text

    with resources.path(__package__, 'creature1_nondefault_gem_affliction_life.png') as path:
        ocr_test_frame(path, manage_spell_gems_ui)
    manage_spell_gems_ui.speak_auto()
    assert "default" not in audio_system_test.last_text


def test_creature_name_spoken_when_changing_creatures(audio_system_test, manage_spell_gems_ui):
    with resources.path(__package__, 'creature1_nondefault_gem_affliction_life.png') as path:
        ocr_test_frame(path, manage_spell_gems_ui)
    manage_spell_gems_ui.speak_auto()
    creature1_name = "Omelette"
    assert creature1_name in audio_system_test.last_text

    # creature 1 name goes away next spoken frame
    with resources.path(__package__, 'creature2_default_spell_death_blossom_nature.png') as path:
        ocr_test_frame(path, manage_spell_gems_ui)
    manage_spell_gems_ui.speak_auto()
    assert creature1_name not in audio_system_test.last_text


    with resources.path(__package__, 'creature2_default_spell_death_blossom_nature.png') as path:
        ocr_test_frame(path, manage_spell_gems_ui)
    manage_spell_gems_ui.speak_auto()
    creature2_name = "Melon"
    assert creature2_name in audio_system_test.last_text



def test_what_to_do_menu_detected(audio_system_test, manage_spell_gems_ui):
    with resources.path(__package__, 'what_to_do_make_default_selection.png') as path:
        ocr_test_frame(path, manage_spell_gems_ui)
    manage_spell_gems_ui.speak_auto()
    make_default_text = "Make default selection."
    assert audio_system_test.last_text == make_default_text

    # go back to spell selection
    with resources.path(__package__, 'creature2_default_spell_death_blossom_nature.png') as path:
        ocr_test_frame(path, manage_spell_gems_ui)
    manage_spell_gems_ui.speak_auto()
    assert audio_system_test.last_text != make_default_text

    with resources.path(__package__, 'what_to_do_make_default_selection.png') as path:
        ocr_test_frame(path, manage_spell_gems_ui)
    manage_spell_gems_ui.speak_auto()
    assert audio_system_test.last_text == make_default_text

