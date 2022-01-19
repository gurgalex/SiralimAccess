from typing import Union

from subot.ui_areas.AnointmentClaimUI import AnointmentClaimUI
from subot.ui_areas.CodexGeneric import CodexGeneric, CodexSpells
from subot.ui_areas.CreatureReorderSelectFirst import OCRCreatureRecorderSelectFirst, OCRCreatureRecorderSwapWith
from subot.ui_areas.FieldItemSelect import FieldItemSelectUI
from subot.ui_areas.InspectScreenUI import InspectScreenUI
from subot.ui_areas.OCRGodForgeSelect import OCRGodForgeSelectSystem
from subot.ui_areas.PerkScreen import PerkScreen
from subot.ui_areas.battle.cast import BattleCastUI
from subot.ui_areas.creatures_display import OCRCreaturesDisplaySystem
from subot.ui_areas.enchanter.choose_enchantment import SpellChooseEnchantmentUI
from subot.ui_areas.enchanter.disenchant import SpellDisenchantUI
from subot.ui_areas.enchanter.enchant_screen import SpellEnchantUI
from subot.ui_areas.enchanter.upgrade import SpellUpgradeUI
from subot.ui_areas.equip_spell_gem import EquipSpellGemUI
from subot.ui_areas.manage_spell_gems import ManageSpellGemsUI
from subot.ui_areas.realm_select import OCRRealmSelect
from subot.ui_areas.refinery.spell import SalvageSpellUI
from subot.ui_areas.summoning import OcrSummoningSystem
from subot.ui_areas.OcrUnknownArea import OcrUnknownArea
from subot.ui_areas.enchanter.spell_craft_screen import SpellCraftUI

OCR_UI_SYSTEMS = Union[
    OCRCreatureRecorderSelectFirst, OCRCreatureRecorderSwapWith, OCRGodForgeSelectSystem, OCRCreaturesDisplaySystem, OcrSummoningSystem, OcrUnknownArea, OCRRealmSelect, PerkScreen, AnointmentClaimUI, FieldItemSelectUI,
    # codex
    CodexGeneric, CodexSpells,
    # battle screens
    InspectScreenUI, BattleCastUI,
    # spell screens
    SpellCraftUI, SpellEnchantUI, SpellDisenchantUI, SpellUpgradeUI, SpellChooseEnchantmentUI,
    # creatures menu
    ManageSpellGemsUI, EquipSpellGemUI,
    # refinery
    SalvageSpellUI,
]


