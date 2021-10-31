from typing import Union

from subot.ui_areas.CreatureReorderSelectFirst import OCRCreatureRecorderSelectFirst, OCRCreatureRecorderSwapWith
from subot.ui_areas.OCRGodForgeSelect import OCRGodForgeSelectSystem
from subot.ui_areas.creatures_display import OCRCreaturesDisplaySystem
from subot.ui_areas.summoning import OcrSummoningSystem

OCR_UI_SYSTEMS = Union[
    OCRCreatureRecorderSelectFirst, OCRCreatureRecorderSwapWith, OCRGodForgeSelectSystem, OCRCreaturesDisplaySystem, OcrSummoningSystem]