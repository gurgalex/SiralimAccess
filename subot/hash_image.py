from pathlib import Path
import cv2
from dataclasses import dataclass
import numpy as np
from typing import NewType
from numpy.typing import ArrayLike

@dataclass(frozen=True)
class ImageInfo:
    short_name: str
    long_name: str

from collections import UserDict

class HashDecor(UserDict):

    def hash_grayscale_img(self, greyscale_img: ArrayLike, img_info: ImageInfo):
        self.data[greyscale_img.tobytes()] = ImageInfo

    def hash_transparent_bgra(self, img_bgra: ArrayLike, img_info: ImageInfo):
        """Uses the transparency layer as the image mask.
        Converts the image to grayscale and stores the bytes as a key for later matching
        Stores the `img_info` as the value
        """
        alpha_channel = img_bgra[:, :, 3]
        _, mask = cv2.threshold(alpha_channel, 254, 255, cv2.THRESH_BINARY)  # binarize mask
        color = img_bgra[:, :, :3]
        img_color_masked = cv2.bitwise_and(color, color, mask=mask)

        img_gray_masked = cv2.cvtColor(img_color_masked, cv2.COLOR_BGR2GRAY)

        self.data[img_gray_masked.tobytes()] = img_info


    def get_greyscale(self, img_gray: ArrayLike) -> ImageInfo:
        return self.data[img_gray.tobytes()]

    def get_from_transparent_rgba(self, img) -> ImageInfo:
        alpha_channel = img[:, :, 3]
        _, mask = cv2.threshold(alpha_channel, 254, 255, cv2.THRESH_BINARY)  # binarize mask
        color = img[:, :, :3]
        img = cv2.bitwise_and(color, color, mask=mask)

        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return self.data[img.tobytes()]


def cache_image_hashes_of_decorations() -> HashDecor:
    hash_decor = HashDecor()
    cv2.namedWindow('title', cv2.WINDOW_GUI_EXPANDED)
    for img_path in Path("../assets_padded/").glob("*/*.png"):

        img = cv2.imread(img_path.as_posix(), cv2.IMREAD_UNCHANGED)


        metadata = ImageInfo(name=img_path.stem)
        hash_decor.hash_transparent_bgra(img, metadata)

    return hash_decor

class CastleDecorationDict(UserDict):
    """Stores castle decorations for exact matching
    On get and set it will set any pixels that match the castle tile to 0.
    Setting the pixels to 0 prevents false negative matches if the floor tile and screenshot share the
    the pixel value in a position
    """

    def __init__(self, val=None, castle_tile_gray=np.typing.ArrayLike):
        """:param castle_tile_gray: numpy array of grayscale image of the current castle tile"""
        if val is None:
            val = {}
        self.castle_tile_gray = castle_tile_gray
        super().__init__(val)

    def insert_transparent_bgra_image(self, img_bgra: np.typing.ArrayLike, img_info: ImageInfo):

        # extra alpha channel as mask
        alpha_channel = img_bgra[:, :, 3]
        _, mask = cv2.threshold(alpha_channel, 254, 255, cv2.THRESH_BINARY)  # binarize mask
        # extract bgr color channels
        color = img_bgra[:, :, :3]

        img_color_masked = cv2.bitwise_and(color, color, mask=mask)
        img_gray_masked = cv2.cvtColor(img_color_masked, cv2.COLOR_BGR2GRAY)

        # set same value pixels to 0
        gray_mask = cv2.absdiff(img_gray_masked, self.castle_tile_gray)
        img_after_exclusion: ArrayLike = cv2.bitwise_and(img_gray_masked, img_gray_masked, mask=gray_mask)

        # do not add the floor tile itself as a hash, as that will match all completely black tiles
        if np.all((img_after_exclusion == 0)):
            return

        self.data[img_after_exclusion.tobytes()] = img_info

    def get_greyscale(self, img_gray: ArrayLike) -> ImageInfo:
        """
        :param img_gray The unaltered grayscale image that hasn't had same pixels stripped
        according to `self.castle_tile_gray`
        """
        screenshot_diff_from_floor = cv2.absdiff(img_gray, self.castle_tile_gray)
        img_excluded = cv2.bitwise_and(img_gray, img_gray, mask=screenshot_diff_from_floor)
        return self.data[img_excluded.tobytes()]


if __name__ == "__main__":
    hashes = cache_image_hashes_of_decorations()

    test_path = "assets_padded/misc/Bastion Wisp-frame2.png"
    metadata = ImageInfo(name=Path(test_path).stem)
    test_img = cv2.imread(test_path, cv2.IMREAD_UNCHANGED)
    test_img_grayscale = cv2.cvtColor(test_img, cv2.COLOR_BGR2GRAY)

    hashes.hash_transparent_bgra(test_img, metadata)

    res = hashes.get_from_transparent_rgba(test_img)
    res_gray = hashes.get_greyscale(test_img_grayscale)
    print("FINISHED")
