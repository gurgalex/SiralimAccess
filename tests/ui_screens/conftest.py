import pytest

from subot.ocr import OCR
from subot.settings import Config
from tests.ui_screens.utils import AudioSystemTest


@pytest.fixture
def audio_system_test() -> AudioSystemTest:
    return AudioSystemTest()


@pytest.fixture(scope="session")
def ocr_engine():
    return OCR()


@pytest.fixture
def config():
    return Config()

