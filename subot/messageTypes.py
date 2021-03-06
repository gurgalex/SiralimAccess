from dataclasses import field, dataclass
from enum import Enum, auto
import numpy as np
from typing import Union

from subot.datatypes import Rect


class MessageType(Enum):
    NEW_FRAME = auto()
    SCAN_FOR_ITEMS = auto()
    CHECK_WHAT_REALM_IN = auto()
    DRAW_DEBUG = auto()
    WINDOW_DIM = auto()
    SHUTDOWN = auto()

@dataclass()
class CheckWhatRealmIn:
    type: MessageType = field(init=False, default=MessageType.CHECK_WHAT_REALM_IN)

@dataclass()
class ScanForItems:
    type: MessageType = field(init=False, default=MessageType.SCAN_FOR_ITEMS)

@dataclass()
class DrawDebug:
    type: MessageType = field(init=False, default=MessageType.DRAW_DEBUG)

@dataclass()
class NewFrame:
    """A new frame has arrived for processing"""
    type: MessageType = field(init=False, default=MessageType.NEW_FRAME)
    frame: np.ndarray


MessageImpl = Union[NewFrame, ScanForItems]


@dataclass(frozen=True)
class Shutdown:
    type: MessageType = MessageType.SHUTDOWN


@dataclass(frozen=True)
class Pause:
    pass


@dataclass(frozen=True)
class Resume:
    pass


@dataclass(frozen=True)
class WindowDim:
    mss_dict: dict


ConfigMsg = Union[WindowDim, Shutdown, Pause, Resume]
