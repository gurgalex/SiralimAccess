import enum
from enum import auto
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn
import cv2


def read_version() -> str:
    with open(Path(__file__).parent.parent.joinpath("VERSION")) as f:
        return f.read().strip()


def extract_mask_from_rgba_img(img):

    alpha_channel = img[:, :, 3]
    _, mask = cv2.threshold(alpha_channel, 1, 255, cv2.THRESH_BINARY)  # binarize mask
    return mask
    color = img[:, :, :3]
    img = cv2.bitwise_and(color, color, mask=mask)

    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def as_tuple(self):
        return self.x, self.y


class PlayerDirection(enum.Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()


def assert_never(x: NoReturn) -> NoReturn:
    raise AssertionError("Unhandled type: {}".format(type(x).__name__))
