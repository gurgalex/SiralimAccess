from enum import Enum, auto
from typing import Union, Optional, Type

from subot.ui_areas.CreatureReorderSelectFirst import OCRCreatureRecorderSelectFirst, OCRCreatureRecorderSwapWith
from subot.ui_areas.OCRGodForgeSelect import OCRGodForgeSelectSystem
from subot.ui_areas.creatures_display import OCRCreaturesDisplaySystem
from subot.ui_areas.summoning import OcrSummoningSystem
from subot.ui_areas.OcrUnknownArea import OcrUnknownArea


OCR_UI_SYSTEMS = Union[
    OCRCreatureRecorderSelectFirst, OCRCreatureRecorderSwapWith, OCRGodForgeSelectSystem, OCRCreaturesDisplaySystem, OcrSummoningSystem, OcrUnknownArea]


class OCRMode(Enum):
    SUMMON = (OcrSummoningSystem,)
    UNKNOWN = (OcrUnknownArea,)
    INSPECT = (None,)
    CREATURES_DISPLAY = (OCRCreaturesDisplaySystem,)
    SELECT_GODFORGE_AVATAR = (OCRGodForgeSelectSystem,)
    CREATURE_REORDER_SELECT = (OCRCreatureRecorderSelectFirst,)
    CREATURE_REORDER_WITH = (OCRCreatureRecorderSwapWith,)

    def __init__(self, system: Optional[Type[OCR_UI_SYSTEMS]]):
        self.system = system
