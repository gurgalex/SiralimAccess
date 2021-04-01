from typing import Union, List

import cv2
import mss
import numpy
import time

import skimage
import win32gui
import math

from dataclasses import dataclass

TILE_SIZE = 32

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
    """Returns Rect class of the Siralim Ultimate window. Coordinates are without title bar and borders"""
    su_hwnd = win32gui.FindWindow(None, "Siralim Ultimate")
    if su_hwnd is None:
        raise AssertionError("Siralim Ultimate is not open")
    rect = win32gui.GetWindowRect(su_hwnd)
    clientRect = win32gui.GetClientRect(su_hwnd)
    windowOffset = math.floor(((rect[2]-rect[0])-clientRect[2])/2)
    titleOffset = ((rect[3]-rect[1])-clientRect[3]) - windowOffset
    newRect = (rect[0]+windowOffset, rect[1]+titleOffset, rect[2]-windowOffset, rect[3]-windowOffset)

    return Rect(x=newRect[0], y=newRect[1], w=newRect[2] - newRect[0], h=newRect[3] - newRect[1])


class Bot:
    def __init__(self):
        # Used to only analyze the SU window
        self.su_client_rect = get_su_client_rect()
        self.player_position: Rect = Bot.compute_player_position(self.su_client_rect)
        self.frame: numpy.typing.ArrayLike = None

        self.grid_rect = Bot.compute_grid_rect(bottom_right_tile=Bot.bottom_right_tile(self.player_position),
                                               top_left_tile=Bot.top_left_tile(self.player_position))
        print(f"{self.player_position=}")

    @staticmethod
    def compute_player_position(client_dimensions: Rect) -> Rect:
        """The top-left of the player sprite is drawn at the center of the screen (relative to window)"""

        # the player is always in the center of the window of the game
        #offset
        #######xxxxx###
        #######xxCxx###
        #######xxxxx###

        return Rect(x=round(client_dimensions.w/2), y=round(client_dimensions.h/2),
                    w=TILE_SIZE, h=TILE_SIZE)

    @staticmethod
    def top_left_tile(player_position: Rect) -> Point:

        player_x = player_position.top_left().x
        player_y = player_position.top_left().y

        top_left_pt =  Point(x=player_x - (player_x // TILE_SIZE) * TILE_SIZE,
                     y=player_y - (player_y // TILE_SIZE) * TILE_SIZE)
        print(f"{top_left_pt=}")
        return top_left_pt

    @staticmethod
    def bottom_right_tile(player_position: Rect) -> Point:
        """Returns top-left coords of bottom-most rectangle"""
        player_x = player_position.top_left().x
        player_y = player_position.top_left().y
        bottom_right_pt = Point(x=player_x + (player_x // TILE_SIZE) * TILE_SIZE - TILE_SIZE,
                     y=player_y + (player_y // TILE_SIZE) * TILE_SIZE - TILE_SIZE)
        print(f"{bottom_right_pt=}")
        return bottom_right_pt




    @staticmethod
    def compute_grid_rect(top_left_tile: Point, bottom_right_tile: Point) -> Rect:
        """slice of image that is is occuppied by realm tiles
        Rect returns is the (x,y) coords of the top-left tile, the width and height includes the tile size of the bottom-right tile
        All useable tile pixels
        """
        print(f"width = {bottom_right_tile.x=} - {top_left_tile.x=}")
        width = bottom_right_tile.x - top_left_tile.x + TILE_SIZE
        print(f"{width=}")
        height = bottom_right_tile.y - top_left_tile.y + TILE_SIZE
        return Rect(x=top_left_tile.x, y=top_left_tile.y, w=width, h=height)

    def draw_tiles(self):

        chunk_shape = (TILE_SIZE, TILE_SIZE)
        print(f"{self.frame.shape}")
        # skimage.util.view_as_blocks(self.frame[self.top_left_tile().x:, ],)


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
            # TemplateMeta(name="lister-shipwreck", path="assets/lister-shipwreck-inner.png", color=red),
            # TemplateMeta(name="teleportation shrine", path="assets/teleportation-shrine-inner.png", color=blue),
            # TemplateMeta(name="Big Chest", path="assets/aurum-big-chest.png", color=yellow),
            # TemplateMeta(name="Altar", path="assets/lister-god-part.png", color=green),
            # TemplateMeta(name="Altar", path="assets/gonfurian-altar-min.png", color=yellow),
            # TemplateMeta(name="Altar", path="assets/aurum-altar.png", color=yellow),
            # TemplateMeta(name="Nether Portal", path="assets/nether-portal-frame1.png", color=orange),
            # TemplateMeta(name="Inscription Slate", path="assets/inscription-slate-inner.png", color=purple),
            # TemplateMeta(name="Treasure Map", path="assets/treasure_map_autum.png", color=orange),
            #
            # TemplateMeta(name="Divination Candle", path="assets/divination-candle-inner.png", color=orange),
            # # NPCs in castle
            # TemplateMeta(name="Menagerie NPC", path="assets/farm-npc-min.png", color=orange),
            TemplateMeta(name="Tile", path="assets/floortiles/Yseros' Floor Tile-frame1.png", color=red),

        }


        mon = {"top": self.su_client_rect.y, "left": self.su_client_rect.x, "width": self.su_client_rect.w, "height": self.su_client_rect.h}
        title = "[MSS] SU Vision"
        with mss.mss() as sct:
            while True:
                shot = sct.grab(mon)
                img_rgb = numpy.asarray(shot)
                self.frame = img_rgb
                bot.draw_tiles()
                img = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)

                for template_struct in templates:
                    template = cv2.imread(template_struct.path, 0)

                    height, width = template.shape[::-1]

                    res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
                    threshold = 0.80

                    loc = np.where(res >= threshold)
                    for pt in zip(*loc[::-1]):
                        cv2.rectangle(img_rgb, pt, (pt[0] + height, pt[1] + width), template_struct.color, 1)
                        # label finding with text
                        # cv2.putText(img_rgb, template_struct.name, (pt[0], pt[1] - 10), cv2.FONT_HERSHEY_PLAIN, 2, (0, 0, 0), 2)
                        # print(f"tile top-left: ({pt[0]},{pt[1]})")

                        # print directions
                        # print(f"player is ({int(round((pt[0]-self.player_position.top_left().x)/TILE_SIZE))},{int(round((pt[1]-self.player_position.top_left().y)/TILE_SIZE))}) from {template_struct.name}")
                        pass



                # label player position
                cv2.rectangle(img_rgb, self.player_position.top_left().as_tuple(),
                              self.player_position.bottom_right().as_tuple(), (255, 255, 255), 1)
                # label finding with text

                cv2.imshow(title, img_rgb)
                if cv2.waitKey(20) & 0xFF == ord("q"):
                    cv2.destroyAllWindows()
                    break


if __name__ == "__main__":
    bot = Bot()
    print(f"{bot.su_client_rect=}")
    print(f"{bot.grid_rect=}")

    bot.run()