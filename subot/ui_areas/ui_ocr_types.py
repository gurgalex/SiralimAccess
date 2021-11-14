from typing import Union

from subot.ui_areas.CodexGeneric import CodexGeneric
from subot.ui_areas.CreatureReorderSelectFirst import OCRCreatureRecorderSelectFirst, OCRCreatureRecorderSwapWith
from subot.ui_areas.OCRGodForgeSelect import OCRGodForgeSelectSystem
from subot.ui_areas.PerkScreen import PerkScreen
from subot.ui_areas.creatures_display import OCRCreaturesDisplaySystem
from subot.ui_areas.realm_select import OCRRealmSelect
from subot.ui_areas.summoning import OcrSummoningSystem
from subot.ui_areas.OcrUnknownArea import OcrUnknownArea

OCR_UI_SYSTEMS = Union[
    OCRCreatureRecorderSelectFirst, OCRCreatureRecorderSwapWith, OCRGodForgeSelectSystem, OCRCreaturesDisplaySystem, OcrSummoningSystem, OcrUnknownArea, CodexGeneric, OCRRealmSelect, PerkScreen]


