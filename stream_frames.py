from typing import Union, List

import cv2
import mss
import numpy
import time
import win32gui
import math

from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateMeta:
    name: str
    path: str
    color: tuple


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def as_tuple(self):
        return self.x, self.y


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



def get_su_client_rect() -> Rect:
    su_hwnd = win32gui.FindWindow(None, "Siralim Ultimate")
    if su_hwnd is None:
        raise AssertionError("Siralim Ultimate is not open")
    rect = win32gui.GetClientRect(su_hwnd)
    print(rect)
    su_rect = Rect(x=rect[0], y=rect[1], w=rect[2], h=rect[3])
    return su_rect


class Bot:
    def __init__(self):
        # Used to only analyze the SU window
        su_rect = get_su_client_rect()
        self.player_position: Rect = Bot.compute_player_position(su_rect)
        print(f"{self.player_position=}")

    @staticmethod
    def compute_player_position(client_dimensions: Rect) -> Rect:
        """The top-left of the player sprite is drawn at the center of the screen"""

        # the player is always in the center of the window of the game
        #offset
        #######xxxxx###
        #######xxCxx###
        #######xxxxx###

        return Rect(x=int(client_dimensions.w/2), y=int(client_dimensions.h/2),
                    w=32, h=32)

    def run(self):
        # 800x600 windowed mode

        import cv2
        from pathlib import Path
        import numpy as np
        from matplotlib import pyplot as plt

        #BGR colors
        blue = (255, 0, 0)
        purple = (255, 0, 255)
        green = (0, 255, 0)
        red = (0, 0, 255)
        yellow = (0, 255, 255)
        orange = (0, 215, 255)

        templates = {
            # TemplateMeta(name="aurem-tile", path="assets/template-of-lies-floor-tile1.png", color=red),
            TemplateMeta(name="lister-shipwreck", path="assets/lister-shipwreck-inner.png", color=red),
            TemplateMeta(name="teleportation shrine", path="assets/teleportation-shrine-inner.png", color=blue),
            TemplateMeta(name="Big Chest", path="assets/aurum-big-chest.png", color=yellow),
            TemplateMeta(name="Altar", path="assets/lister-god-part.png", color=green),
            TemplateMeta(name="Altar", path="assets/gonfurian-altar-min.png", color=yellow),
            TemplateMeta(name="Altar", path="assets/aurum-altar.png", color=yellow),
            TemplateMeta(name="Nether Portal", path="assets/nether-portal-frame1.png", color=orange),
            TemplateMeta(name="Inscription Slate", path="assets/inscription-slate-inner.png", color=purple),
            TemplateMeta(name="Treasure Map", path="assets/treasure_map_autum.png", color=orange),

            TemplateMeta(name="Divination Candle", path="assets/divination-candle-inner.png", color=orange),
            # NPCs in castle
            TemplateMeta(name="Menagerie NPC", path="assets/farm-npc-min.png", color=orange),

        }


        mon = {"top": 38, "left": 0, "width": 958, "height": 483}
        title = "[MSS] SU Vision"
        with mss.mss() as sct:
            while True:
                shot = sct.grab(mon)
                img_rgb = numpy.asarray(shot)
                img = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)

                for template_struct in templates:
                    template = cv2.imread(template_struct.path, 0)

                    height, width = template.shape[::-1]

                    res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
                    threshold = 0.80

                    loc = np.where(res >= threshold)
                    for pt in zip(*loc[::-1]):
                        cv2.rectangle(img_rgb, pt, (pt[0] + height, pt[1] + width), template_struct.color, 2)
                        # label finding with text
                        cv2.putText(img_rgb, template_struct.name, (pt[0], pt[1] - 10), cv2.FONT_HERSHEY_PLAIN, 2, (0, 0, 0), 2)

                        # print directions
                        print(f"player is ({int(round((pt[0]-self.player_position.top_left().x)/32))},{int(round((pt[1]-self.player_position.top_left().y)/32))}) from {template_struct.name}")


                # label player position
                cv2.rectangle(img_rgb, self.player_position.top_left().as_tuple(),
                              self.player_position.bottom_right().as_tuple(), (255, 255, 255), 2)
                # label finding with text

                cv2.imshow(title, img_rgb)
                if cv2.waitKey(25) & 0xFF == ord("q"):
                    cv2.destroyAllWindows()
                    break


if __name__ == "__main__":
    bot = Bot()
    bot.run()