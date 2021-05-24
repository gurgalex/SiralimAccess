from multiprocessing import Process, Queue
import mss
import mss.tools
import queue

import time

def grab_whole_frame(color_frame_queue: Queue) -> None:
    rect = {"top": 0, "left": 0, "width": 1920, "height": 1080}

    should_stop = False

    with mss.mss() as sct:
        while not should_stop:
            # Performance: copying overhead is not an issue for needing a frame at 1-2 FPS
            try:
                color_frame_queue.put_nowait(sct.grab(rect))
            except queue.Full:
                pass
            time.sleep(0.5)

def grab_nearby_player(color_nearby_queue: Queue, nearby_rect: dict):
    """Screenshots the area defined as nearby the player. no more than 8x8 tiles (256pxx256px)
    :param color_nearby_queue Queue used to send recent nearby screenshot to processing code
    :param nearby_rect dict used in mss.grab. keys `top`, `left`, `width`, `height`
    """


    rect = {"top": 0, "left": 0, "width": 256, "height": 256}

    should_stop = False

    with mss.mss() as sct:
        while not should_stop:
            try:
                # Performance: Unsure if 1MB copying at 60FPS is fine
                # Note: Possibly use shared memory if performance is an issue
                color_nearby_queue.put_nowait(sct.grab(rect))
            except queue.Full:
                pass


def save(queue):
    # type: (Queue) -> None
    import time
    import math

    number = 0

    start = time.time()
    while True:
        img = queue.get()
        if img is None:
            break
        number += 1
        if number % 10 == 0:
            end = time.time()
            latency = (end-start)
            print(f"took {math.ceil(latency*1000//10)}ms")
            start = time.time()


def analyze_quest_area(queue: Queue) -> None:
    import time
    import math

    number = 0

    start = time.time()
    while True:
        img = queue.get()
        if img is None:
            break
        number += 1
        end = time.time()
        latency = (end-start)
        print(f"Quest: took {math.ceil(latency*1000)}ms")
        start = time.time()


if __name__ == "__main__":
    # The screenshots queue
    queue = Queue()  # type: Queue

    other_queue: Queue = Queue()
    other_queue2 = Queue()

    # 2 processes: one for grabing and one for saving PNG files
    Process(target=grab_nearby_player, args=(queue,)).start()
    Process(target=save, args=(queue,)).start()

    Process(target=grab_whole_frame, args=(other_queue,)).start()
    Process(target=analyze_quest_area, args=(other_queue,)).start()

