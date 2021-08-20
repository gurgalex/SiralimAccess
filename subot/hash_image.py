import time
from pathlib import Path
import cv2
from collections import UserDict
from dataclasses import dataclass
import numpy as np
from typing import NewType, Optional
from numpy.typing import ArrayLike

from subot.models import SpriteType


@dataclass(frozen=True)
class ImageInfo:
    short_name: str
    long_name: str
    sprite_type: SpriteType


def img_float32(img):
    return img.copy() if img.dtype != 'uint8' else (img / 255.).astype('float32')


def over(fgimg, bgimg):
    fgimg, bgimg = img_float32(fgimg), img_float32(bgimg)
    (fb, fg, fr, fa), (bb, bg, br, ba) = cv2.split(fgimg), cv2.split(bgimg)
    color_fg, color_bg = cv2.merge((fb, fg, fr)), cv2.merge((bb, bg, br))
    alpha_fg, alpha_bg = np.expand_dims(fa, axis=-1), np.expand_dims(ba, axis=-1)

    color_fg[fa == 0] = [0, 0, 0]
    color_bg[ba == 0] = [0, 0, 0]

    a = fa + ba * (1 - fa)
    a[a == 0] = np.NaN
    color_over = (color_fg * alpha_fg + color_bg * alpha_bg * (1 - alpha_fg)) / np.expand_dims(a, axis=-1)
    color_over = np.clip(color_over, 0, 1)
    color_over[a == 0] = [0, 0, 0]

    result_float32 = np.append(color_over, np.expand_dims(a, axis=-1), axis=-1)
    return (result_float32 * 255).astype('uint8')


def overlay_with_transparency(bgimg, fgimg, xmin=0, ymin=0, trans_percent=1):
    '''
    bgimg: a 4 channel image, use as background
    fgimg: a 4 channel image, use as foreground
    xmin, ymin: a corrdinate in bgimg. from where the fgimg will be put
    trans_percent: transparency of fgimg. [0.0,1.0]
    '''
    # we assume all the input image has 4 channels
    assert (bgimg.shape[-1] == 4 and fgimg.shape[-1] == 4)
    fgimg = fgimg.copy()
    roi = bgimg[ymin:ymin + fgimg.shape[0], xmin:xmin + fgimg.shape[1]].copy()

    b, g, r, a = cv2.split(fgimg)

    fgimg = cv2.merge((b, g, r, (a * trans_percent).astype(fgimg.dtype)))

    roi_over = over(fgimg, roi)

    result = bgimg.copy()
    result[ymin:ymin + fgimg.shape[0], xmin:xmin + fgimg.shape[1]] = roi_over
    return result

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

    # check if alpha blending is required
    a: ArrayLike
    alpha_sum = np.sum(a)
    has_partial_transparency = alpha_sum % 255 != 0
    if has_partial_transparency:
        print("using expensive partial transparnecy fn")
        result = overlay_with_transparency(bgimg=background_img, fgimg=img_to_overlay_t)
        return result[:, :, :3]

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


hasher = cv2.img_hash.PHash_create()


def compute_phash(floor_tile: np.typing.ArrayLike, img_bgra, overlay: Optional[Overlay]) -> int:
    if img_bgra.shape != (32, 32, 4):
        raise ValueError(f"image to hash is not one tile worth (32,32,4) !={img_bgra.shape=}")

    pasted_img_color = overlay_transparent(background_img=floor_tile, img_to_overlay_t=img_bgra)
    pasted_img_gray = cv2.cvtColor(pasted_img_color, cv2.COLOR_BGR2GRAY)

    # blend overlay image on top of bg tile + fg sprite
    if overlay:
        overlay_tile = overlay.tile
        alpha = overlay.alpha
        pasted_img_color = cv2.addWeighted(pasted_img_color, alpha, overlay_tile, 1 - alpha, 0.0)
        pasted_img_gray = cv2.cvtColor(pasted_img_color, cv2.COLOR_BGR2GRAY)

    img_hash = hasher.compute(pasted_img_gray)

    # convert to int
    return int.from_bytes(img_hash, byteorder='big', signed=True)


def compute_hash(img_gray: ArrayLike) -> int:
    img_hash = hasher.compute(img_gray)
    hash_int = int.from_bytes(img_hash, byteorder='big', signed=True)
    return hash_int


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
        self.similar_hashes = 0
        # self.hasher = cv2.img_hash.PHash_create()
        super().__init__(val)

    def insert_transparent_bgra_image(self, img_bgra: np.typing.ArrayLike, img_info: ImageInfo) -> Optional[list[int]]:
        if not self.floor_info:
            return

        generated_hashes = []
        for ct, floor_tile in enumerate(self.floor_info.floortiles):
            computed_hash = compute_phash(floor_tile, img_bgra, self.floor_info.overlay)
            if computed_hash in self.data:
                self.similar_hashes += 1
            generated_hashes.append(computed_hash)
            self.data[computed_hash] = img_info
        return generated_hashes

    def get_greyscale(self, img_gray: ArrayLike) -> ImageInfo:
        """
        :param img_gray The unaltered grayscale image that hasn't had same pixels stripped
        according to `self.castle_tile_gray`
        """
        img_hash = hasher.compute(img_gray)
        hash_int = int.from_bytes(img_hash, byteorder='big', signed=True)
        return self.data[hash_int]


if __name__ == "__main__":
    pass