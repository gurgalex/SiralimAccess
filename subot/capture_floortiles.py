import mss
import cv2
import numpy as np
from main import Bot
title = "SU Vision"
with mss.mss() as sct:
    bot = Bot()
    player_pos = bot.player_position
    cv2.namedWindow(title, cv2.WINDOW_GUI_NORMAL)
    pause_collection = True
    c_title = "controls"

    decoration_mon = {"top": bot.su_client_rect.y + bot.player_position.y + 32, "left": bot.su_client_rect.x + bot.player_position.x + 32, "width": 32, "height": 32}
    print(f"{decoration_mon=}")

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
        frame += 1
        print("new image found")
        print(f"captured {len(hashes)} images")

        cv2.imwrite(f"assets_padded/realm-tiles-manual/Gonfurian-frame{frame}.png", decoration_img)



        if cv2.waitKey(25) & 0xFF == ord("Q"):
            cv2.destroyAllWindows()
            break
