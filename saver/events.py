from __future__ import annotations
from pyee import EventEmitter
from dataclasses import dataclass

ee = EventEmitter()

@dataclass(frozen=True)
class QuestReceivedRaw:
    desc: str


@dataclass(frozen=True)
class QuestReceived:
    db_id: int
