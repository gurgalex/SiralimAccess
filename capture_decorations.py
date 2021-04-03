from typing import Union, List

import cv2
import mss
import numpy
import time
import win32gui
import math
import pytesseract
from stream_frames import TILE_SIZE
import numpy as np
from numpy.typing import ArrayLike
from time import sleep

from stream_frames import Bot, Rect

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract'


def detect_green_text(image) -> np.array:
    """Using a source image of RGB color, extract highlighted menu items which are a green color"""
    lower_green = np.array([60, 50, 100])
    upper_green = np.array([60, 255, 255])

    img = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(img, lower_green, upper_green)
    mask = cv2.bitwise_not(mask)
    return mask


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
    crop_img = background_marked_as_transparent_img[:next_multiple(y+h, TILE_SIZE), :next_multiple(x+w, TILE_SIZE)]
    cv2.imwrite(f"{filename}", crop_img)
    return crop_img



mon = {"top": 38, "left": 0, "width": 1000, "height": 1000}
title = "SU Vision"
with mss.mss() as sct:
    bot = Bot()
    player_pos = bot.player_position
    cv2.namedWindow(title, cv2.WINDOW_GUI_EXPANDED)
    pause_collection = True
    c_title = "controls"

    decoration_mon = {"top": bot.su_client_rect.y + bot.player_position.y, "left": bot.su_client_rect.x + bot.player_position.x, "width": 256, "height": 256}
    print(f"{decoration_mon=}")

    old_line = ""

    hashes = set()
    frame = 1

    while True:
        if cv2.waitKey(10) & 0xFF == ord("p"):
            pause_collection = not pause_collection
            if pause_collection:
                print("Collection paused")
            else:
                print("Collection started")

        decoration_shot = sct.grab(decoration_mon)
        decoration_img = np.asarray(decoration_shot)
        if pause_collection:
            cv2.imshow(title, decoration_img)
            continue

        img_gray = cv2.cvtColor(decoration_img, cv2.COLOR_BGR2GRAY)
        old_len_hash = len(hashes)
        hashes.add(img_gray.tobytes())

        cv2.imshow(title, decoration_img)
        if len(hashes) == old_len_hash:
            continue
        print("new image found")
        print(f"captured {len(hashes)} images")



        should_ocr = True



        if not should_ocr:
            continue

        shot = sct.grab(mon)
        img_rgb = numpy.asarray(shot)
        selected_menu_option_img = detect_green_text(img_rgb)

        text = pytesseract.image_to_string(selected_menu_option_img, lang="eng")
        text = text.strip("\x0c")
        text = text.strip()
        single_line = text.split("\n")[0]

        if text:
            filename = ""
            if old_line != single_line:
                # print(f'Select: {single_line}')
                old_line = single_line
                frame = 1
            else:
                frame += 1
            filename = f"assets_padded/misc/{single_line}-frame{frame}.png"
            cropped_decoration_mg = save_decoration_as_transparent_cropped(decoration_img, filename=filename)
            print(f"saved image as {filename}")
            cv2.imshow(title, cropped_decoration_mg)
        # cv2.imshow(title, selected_menu_option_img)
        if cv2.waitKey(25) & 0xFF == ord("Q"):
            cv2.destroyAllWindows()
            break
