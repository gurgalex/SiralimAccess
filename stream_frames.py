import cv2
import mss
import numpy
import time

from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateMeta:
    name: str
    path: str
    color: tuple


def screen_record_efficient():
    # 800x600 windowed mode

    import cv2
    from pathlib import Path
    import numpy as np
    from matplotlib import pyplot as plt

    blue = (255, 0, 0)
    green = (0, 255, 0)
    red = (0, 0, 255)

    templates = {
        TemplateMeta(name="lister-shipwreck", path="assets/lister-shipwreck.png", color=red),
        TemplateMeta(name="lister-teleportation-shrine", path="assets/lister-teleportation-shrine.png", color=blue),
    }

    # template = cv2.imread(Path('assets').joinpath('lister-teleportation-shrine.png').as_posix(), 0)
    mon = {"top": 40, "left": 0, "width": 800, "height": 640}
    title = "[MSS] SU Vision"
    with mss.mss() as sct:
        while True:
            shot = sct.grab(mon)
            img_rgb = numpy.asarray(shot)
            img = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)

            for template_struct in templates:
                template = cv2.imread(template_struct.path, 0)

                height, width = template.shape[::-1]

                res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)

                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                # print(f"{min_val=}, {max_val=}, {min_loc=}, {max_loc=}")

                top_left = max_loc  # Change to max_loc for all except for TM_SQDIFF
                bottom_right = (top_left[0] + width, top_left[1] + height)
                if max_val > 0.80:
                    # put rectangle around finding
                    cv2.rectangle(img_rgb, top_left, bottom_right, template_struct.color, 5)

                    # label finding with text
                    cv2.putText(img_rgb, template_struct.name, (top_left[0], top_left[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)

            cv2.imshow(title, img_rgb)
            if cv2.waitKey(25) & 0xFF == ord("q"):
                cv2.destroyAllWindows()
                break

print("MSS:", screen_record_efficient())
