from pathlib import Path
from typing import Union, List

import cv2
import mss
import pytesseract
from main import TILE_SIZE
import numpy as np

from main import Bot
from subot.datatypes import Rect
from background_subtract import subtract_background_color_tile


pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract'

MENU_CAPTURE_AREA = {"top": 38, "left": 0, "width": 1000, "height": 1000}


def next_multiple(number: int, multiple: int) -> int:
    return multiple * (1 + (number - 1) // multiple)


def save_decoration_as_transparent_cropped(decor_rgba_image, filename):
    gray = cv2.cvtColor(decor_rgba_image, cv2.COLOR_RGB2GRAY)

    # All non-black pixels are set as opaque (visible), all others are set as transparent (0) in the alpha channel
    _, alpha = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY)
    background_marked_as_transparent_img = cv2.bitwise_and(decor_rgba_image, decor_rgba_image, mask=alpha)

    # find minimum crop rectangle to fit decoration in
    points = cv2.findNonZero(alpha)
    x, y, w, h = cv2.boundingRect(points)

    # pad image in 32 pixel dimensions in 32 px increments
    crop_img = background_marked_as_transparent_img[:next_multiple(y + h, TILE_SIZE),
               :next_multiple(x + w, TILE_SIZE)]
    cv2.imwrite(f"{filename}", crop_img)
    return crop_img


class Capture:
    def __init__(self):
        self.title = "SU CAPTURE"
        self.decoration_img = None
        self.menu_img_rgb = None
        self.old_line = ""
        self.frame = 1
        self.castle_tile = cv2.imread("../assets_padded/floortiles/Zonte's Floor Tile-frame1.png", cv2.IMREAD_UNCHANGED)



    def detect_green_text(self, image) -> np.array:
        """Using a source image of RGB color, extract highlighted menu items which are a green color"""
        lower_green = np.array([60, 50, 100])
        upper_green = np.array([60, 255, 255])

        img = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(img, lower_green, upper_green)
        mask = cv2.bitwise_not(mask)
        return mask

    def capture_decoration(self, folder: Path):
        selected_menu_option_img = self.detect_green_text(self.menu_img_rgb)

        text = pytesseract.image_to_string(selected_menu_option_img, lang="eng")
        text = text.strip("\x0c")
        text = text.strip()
        single_line = text.split("\n")[0]
        print(f"Got text: {single_line}")

        if text:
            if self.old_line != single_line:
                # print(f'Select: {single_line}')
                self.old_line = single_line
                self.frame = 1
            else:
                self.frame += 1
            filename = folder.joinpath(f"{single_line}-frame{self.frame}.png").as_posix()
            cropped_decoration_img = save_decoration_as_transparent_cropped(self.decoration_img, filename=filename)
            print(f"saved image as {filename}")
            cv2.imshow(self.title, cropped_decoration_img)

    def capture_costume_no_ocr(self, filepath: Path):

        cleaned_costume_img = subtract_background_color_tile(floor=self.castle_tile, tile=self.decoration_img)
        cv2.imwrite(f"{filepath.as_posix()}", cleaned_costume_img)
        print(f"saved image as {filepath.as_posix()}")
        cv2.imshow(self.title, cleaned_costume_img)

    def save_floortile_img(self, filename: str):
        cv2.imwrite(filename, self.decoration_img)
        self.frame += 1
        print(f"saved floor tile: {filename}")

    def save_tile(self, filepath: Path):
        filepath_str = filepath.as_posix()
        cv2.imwrite(filepath_str, self.decoration_img)
        self.frame += 1
        print(f"saved floor tile: {filepath_str}")

    def run(self):

        folder_to_save_in = Path("../assets_padded/Enemies/Loid/")

        CAPTURE_UNNAMED_TILE = "capture_tile"
        CAPTURE_DECORATION = "capture_decoration"
        CAPTURE_NPC_NO_OCR = "capture_npc_no_ocr"

        with mss.mss() as sct:
            mode = CAPTURE_NPC_NO_OCR
            bot = Bot()
            cv2.namedWindow(self.title, cv2.WINDOW_GUI_EXPANDED)
            pause_collection = True

            if mode == CAPTURE_UNNAMED_TILE or mode == CAPTURE_NPC_NO_OCR:
                capture_area = {"top": bot.su_client_rect.y + bot.player_position.y - TILE_SIZE*0,
                                "left": bot.su_client_rect.x + bot.player_position.x,

                                "width": 32, "height": 32}
                frame = 0
            elif mode == CAPTURE_DECORATION:
                capture_area = {"top": bot.su_client_rect.y + bot.player_position.y, "left": bot.su_client_rect.x + bot.player_position.x, "width": 32, "height": 32}
            print(f"{capture_area=}")

            hashes = set()

            while True:
                if cv2.waitKey(10) & 0xFF == ord("p"):
                    pause_collection = not pause_collection
                    if pause_collection:
                        print("press p to resume capture")
                    else:
                        print("press p to pause capture")

                self.decoration_img = np.asarray(sct.grab(capture_area))
                self.menu_img_rgb = np.asarray(sct.grab(MENU_CAPTURE_AREA))
                if pause_collection:
                    cv2.imshow(self.title, self.decoration_img)
                    continue

                img_gray = cv2.cvtColor(self.decoration_img, cv2.COLOR_BGR2GRAY)
                old_len_hash = len(hashes)
                hashes.add(img_gray.tobytes())

                cv2.imshow(self.title, self.decoration_img)
                if len(hashes) == old_len_hash:
                    continue
                frame += 1
                print("new image found")

                filename = f"{frame}.png"
                filepath = folder_to_save_in.joinpath(filename)

                if mode == CAPTURE_UNNAMED_TILE:
                    self.save_tile(filepath)
                elif mode == CAPTURE_DECORATION:
                    self.capture_decoration(folder=folder_to_save_in)
                elif mode == CAPTURE_NPC_NO_OCR:
                    self.capture_costume_no_ocr(filepath=filepath)
                print(f"captured {len(hashes)} images")
                if cv2.waitKey(25) & 0xFF == ord("Q"):
                    cv2.destroyAllWindows()
                    break

if __name__ == "__main__":
    capture = Capture()
    capture.run()