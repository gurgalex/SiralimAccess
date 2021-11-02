from typing import Optional

import cv2
import numpy as np

YELLOW_CREATURE_SELECT_BGR = np.array([0, 255, 255])
GREEN_CREATURE_SELECT_BGR = np.array([0, 255, 0])


def detect_creature_party_selection(frame: np.typing.ArrayLike) -> Optional[int]:
    """Returns: Which slot the creature is selected in 1-6"""
    # check creature position
    y_start = int(frame.shape[0] * 0.935)
    y_end = int(frame.shape[0] * 0.945)
    x_start = int(frame.shape[1] * 0.00)
    x_end = int(frame.shape[1] * 1)

    creature_pos_indicator_area: np.typing.ArrayLike = frame[y_start:y_end, x_start:x_end]

    mask = cv2.inRange(creature_pos_indicator_area, GREEN_CREATURE_SELECT_BGR, GREEN_CREATURE_SELECT_BGR)
    mask2 = cv2.inRange(creature_pos_indicator_area, YELLOW_CREATURE_SELECT_BGR, YELLOW_CREATURE_SELECT_BGR)
    result = 255 * (mask + mask2)
    combined_mask = result.clip(0, 255).astype('uint8')

    cnts = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours, hierarchy = cnts
    if contours:
        try:
            first = contours[1][0][0][0]
        except IndexError:
            return None
        split_divider = frame.shape[1] // 6
        creature_pos = round((first / split_divider) + 1)
        return creature_pos
    else:
        return None
