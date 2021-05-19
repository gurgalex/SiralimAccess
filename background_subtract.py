import numpy as np
import cv2
import mss
from pathlib import Path
import numpy as np
from numpy.ma import masked_array
import numpy.ma as ma

grayscale_unaltered_title = "grey orig"
# cv2.namedWindow(grayscale_unaltered_title)

def subtract_background_from_tile(tile_gray, floor_background_gray, orig_frame=None):

    # any difference between the floor tile and the game tile
    # Now create a mask of logo and create its inverse mask also

    fg_mask = cv2.absdiff(floor_background_gray, tile_gray)

    dst = cv2.bitwise_and(tile_gray, tile_gray, mask=fg_mask)
    return dst


def subtract_background_color_tile(tile, floor):
    fg_mask = cv2.absdiff(floor, tile)
    # any difference between the floor tile and the game tile
    # Now create a mask of logo and create its inverse mask also

    fg_mask = cv2.absdiff(floor, tile)
    fg_mask = cv2.cvtColor(fg_mask, cv2.COLOR_BGR2GRAY)

    dst = cv2.bitwise_and(tile, tile, mask=fg_mask)
    return dst


if __name__ == "__main__":
    mon = {"top": 38, "left": 0, "width": 1000, "height": 1000}

    with mss.mss() as sct:
        title = "window"
        cv2.namedWindow(title, cv2.WINDOW_GUI_NORMAL)
        floor_tile_path = "assets/floortiles/Yseros' Floor Tile-frame1.png"

        floor_tile = cv2.imread(floor_tile_path, cv2.IMREAD_UNCHANGED)
        # floor_tile_gray = cv2.cvtColor(floor_tile, cv2.COLOR_RGBA2GRAY)
        frame_path = "test_sets/issue-images/treasure-chest-yserors-issue.png"
        frame = cv2.imread(frame_path, cv2.IMREAD_UNCHANGED)
        # frame_gray = cv2.cvtColor(frame, cv2.COLOR_RGBA2GRAY)


        # fgmask = subtract_background_from_tile(tile_gray=frame, floor_background_gray=floor_tile)
        fgmask = subtract_background_color_tile(tile=frame, floor=floor_tile)

        while True:

            cv2.imshow(title, fgmask)
            k = cv2.waitKey(10) & 0xff
            if k == 27:
                break

    cv2.destroyAllWindows()