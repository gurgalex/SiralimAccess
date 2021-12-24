from __future__ import annotations
from dataclasses import dataclass

from saver.save import Save
from subot.utils import Point


@dataclass(frozen=True)
class GameStart:
    pass


@dataclass(frozen=True)
class GameSaved:
    pass


@dataclass(frozen=True)
class PlayerMoved:
    to: Point


@dataclass(frozen=True)
class ObjPlaced:
    obj: str
    placed_at: Point


@dataclass(frozen=True)
class TeleportToRealm:
    spawn_point: Point


@dataclass(frozen=True)
class TeleportToCastle:
    pass


@dataclass(frozen=True)
class InnerPortalEntered:
    """The player entered a portal inside a realm
    future: Portal type + objects spawned in if provided in the future game output
    """
    pass


@dataclass(frozen=True)
class SaveUpdated:
    save: Save