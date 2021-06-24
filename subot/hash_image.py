import time
from pathlib import Path
import cv2
from dataclasses import dataclass
import numpy as np
from typing import NewType, Optional
from numpy.typing import ArrayLike

@dataclass(frozen=True)
class ImageInfo:
    short_name: str
    long_name: str
    filepath: str

from collections import UserDict

def overlay_transparent(background_img, img_to_overlay_t):
    """
    @brief      Overlays a transparant PNG onto another image using CV2

    @param      background_img    The background image
    @param      img_to_overlay_t  The transparent image to overlay (has alpha channel)

    @return     Background image with overlay on top

    adapted from https://gist.github.com/clungzta/b4bbb3e2aa0490b0cfcbc042184b0b4e
    """

    bg_img = background_img[:, :, :3]

    # Extract the alpha mask of the BGRA image, convert to BGR
    b, g, r, a = cv2.split(img_to_overlay_t)
    overlay_color = cv2.merge((b, g, r))

    mask = a

    # Black-out the area behind the overlay in the background image
    img1_bg = cv2.bitwise_and(bg_img, bg_img, mask=cv2.bitwise_not(mask))

    # Mask out the non-transparent pixels from the overlay.
    img2_fg = cv2.bitwise_and(overlay_color, overlay_color, mask=mask)

    # Paste the foreground onto the background
    return cv2.add(img1_bg, img2_fg)

@dataclass()
class Overlay:
    """Info about the tile used for blending on top of the rendered realm"""

    # What percent of this overlay should be blended (how opaque is it)
    alpha: float

    # TILE_SIZExTILE_SIZEx3 overlay image to use for blending
    tile: np.typing.ArrayLike


@dataclass()
class FloorTilesInfo:
    floortiles: list[np.typing.ArrayLike]
    overlay: Optional[Overlay] = None


class RealmSpriteHasher(UserDict):
    """Stores castle decorations for exact matching
    On get and set it will set any pixels that match the castle tile to 0.
    Setting the pixels to 0 prevents false negative matches if the floor tile and screenshot share the
    the pixel value in a position
    """

    def __init__(self, val=None, floor_tiles: Optional[FloorTilesInfo]=None):
        """:param floor_tiles: numpy array of grayscale image of the current castle tile"""
        if val is None:
            val = {}
        self.floor_info = floor_tiles
        self.hasher = cv2.img_hash.PHash_create()
        super().__init__(val)

    def insert_transparent_bgra_image(self, img_bgra: np.typing.ArrayLike, img_info: ImageInfo):

        if not self.floor_info:
            return

        for ct, floor_tile in enumerate(self.floor_info.floortiles):
            pasted_img_color = overlay_transparent(background_img=floor_tile, img_to_overlay_t=img_bgra)
            pasted_img_gray = cv2.cvtColor(pasted_img_color, cv2.COLOR_BGR2GRAY)

            # blend overlay image on top of bg tile + fg sprite
            if self.floor_info.overlay:
                overlay_tile = self.floor_info.overlay.tile
                alpha = self.floor_info.overlay.alpha
                pasted_img_color = cv2.addWeighted(pasted_img_color, alpha, overlay_tile, 1 - alpha, 0.0)
                pasted_img_gray = cv2.cvtColor(pasted_img_color, cv2.COLOR_BGR2GRAY)

            img_hash = self.hasher.compute(pasted_img_gray)

            self.data[img_hash.tobytes()] = img_info

    def get_greyscale(self, img_gray: ArrayLike) -> ImageInfo:
        """
        :param img_gray The unaltered grayscale image that hasn't had same pixels stripped
        according to `self.castle_tile_gray`
        """
        img_hash = self.hasher.compute(img_gray)
        return self.data[img_hash.tobytes()]


if __name__ == "__main__":
    pass