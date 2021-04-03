from pathlib import Path
import cv2
from dataclasses import dataclass
import numpy as np
from typing import NewType
from numpy.typing import ArrayLike

@dataclass(frozen=True)
class ImageInfo:
    name: str

from collections import UserDict

# HashDecor: dict[bytes, ImageInfo] = {}

class HashDecor(UserDict):

    def hash_grayscale_img(self, greyscale_img: ArrayLike, img_info: ImageInfo):
        self.data[greyscale_img.tobytes()] = ImageInfo(name=img_info.name)

    def hash_transparent_bgra(self, img: ArrayLike, img_info: ImageInfo):
        alpha_channel = img[:, :, 3]
        _, mask = cv2.threshold(alpha_channel, 254, 255, cv2.THRESH_BINARY)  # binarize mask
        color = img[:, :, :3]
        img = cv2.bitwise_and(color, color, mask=mask)


        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # cv2.imshow("title", img)

        self.data[img.tobytes()] = ImageInfo(name=img_info.name)


    def get_greyscale(self, img: ArrayLike) -> ImageInfo:
        return self.data[img.tobytes()]

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
    for img_path in Path("assets_padded/").glob("*/*.png"):

        img = cv2.imread(img_path.as_posix(), cv2.IMREAD_UNCHANGED)


        metadata = ImageInfo(name=img_path.stem)
        hash_decor.hash_transparent_bgra(img, metadata)
        from time import sleep
        if cv2.waitKey(10) & 0xFF == ord("p"):
            pass
        # print("sleeping for 1 seconds, should see image")
        # sleep(1)

    return hash_decor

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
