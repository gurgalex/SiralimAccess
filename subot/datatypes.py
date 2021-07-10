from dataclasses import dataclass

from subot.utils import Point


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    def top_left(self) -> Point:
        return Point(x=self.x, y=self.y)

    def bottom_right(self) -> Point:
        return Point(x=self.x + self.w, y=self.y + self.h)

    @classmethod
    def from_cv2_loc(cls, cv2_loc: tuple, w: int, h: int):
        return cls(x=cv2_loc[0], y=cv2_loc[1], w=w, h=h)

    def to_mss_dict(self) -> dict:
        return {"top": self.y, "left": self.x, "width": self.w, "height": self.h}
