from dataclasses import dataclass

import cv2
import numpy as np

def extract_mask_from_rgba_img(img):

    alpha_channel = img[:, :, 3]
    _, mask = cv2.threshold(alpha_channel, 1, 255, cv2.THRESH_BINARY)  # binarize mask
    return mask
    color = img[:, :, :3]
    img = cv2.bitwise_and(color, color, mask=mask)

    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def as_tuple(self):
        return self.x, self.y