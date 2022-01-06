import enum
from dataclasses import dataclass
from enum import auto
from typing import Union


class ActionType(enum.Enum):
    """Actions to control Siralim Access (usually invoked by keyboard keys"""
    READ_SECONDARY_INFO = auto()
    REREAD_AUTO_TEXT = auto()
    READ_ALL_INFO = auto()
    COPY_ALL_INFO = auto()
    HELP = auto()
    SCREENSHOT = auto()
    SILENCE = auto()
    OPEN_CONFIG_LOCATION = auto()
    FORCE_OCR = auto()
    ENEMY_STATS = auto()
    ENEMY_HIGHEST_HP = auto()
    ENEMY_LOWEST_HP = auto()
    ENEMY_SORTED_HP = auto()


@dataclass(frozen=True)
class ReadSecondaryInfoAction:
    kind: ActionType = ActionType.READ_SECONDARY_INFO


@dataclass(frozen=True)
class ReadAllInfoAction:
    kind: ActionType = ActionType.READ_ALL_INFO


@dataclass(frozen=True)
class CopyAllInfoAction:
    kind: ActionType = ActionType.COPY_ALL_INFO

@dataclass(frozen=True)
class ScreenshotAction:
    kind: ActionType = ActionType.SCREENSHOT

@dataclass(frozen=True)
class HelpAction:
    kind: ActionType = ActionType.HELP

@dataclass(frozen=True)
class RereadAutoTextAction:
    kind: ActionType = ActionType.REREAD_AUTO_TEXT

@dataclass(frozen=True)
class OpenConfigLocationAction:
    kind: ActionType = ActionType.OPEN_CONFIG_LOCATION

@dataclass(frozen=True)
class ForceOCRAction:
    kind: ActionType = ActionType.FORCE_OCR

@dataclass(frozen=True)
class EnemyStatsAction:
    enemy_num: int
    kind: ActionType = ActionType.ENEMY_STATS

@dataclass(frozen=True)
class EnemyHighestHPAction:
    kind: ActionType = ActionType.ENEMY_HIGHEST_HP

@dataclass(frozen=True)
class EnemyLowestHPAction:
    kind: ActionType = ActionType.ENEMY_LOWEST_HP

@dataclass(frozen=True)
class EnemySortedHPAction:
    kind: ActionType = ActionType.ENEMY_SORTED_HP


ActionU = Union[ReadSecondaryInfoAction, ReadAllInfoAction, CopyAllInfoAction, RereadAutoTextAction, HelpAction,
                ScreenshotAction, OpenConfigLocationAction, ForceOCRAction,
                EnemyLowestHPAction, EnemyHighestHPAction, EnemyStatsAction, EnemySortedHPAction]
