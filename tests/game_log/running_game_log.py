import queue
import time

from saver.events import ee, QuestReceived, QuestReceivedRaw
from saver.save import load_blank_save, Save
from subot.game_log import GameState, tail_log_file, determine_event, LowLevelEvent, BotMode
from subot.game_log_events import GameSaved, SaveUpdated, ObjPlaced, TeleportToCastle, TeleportToRealm, GameStart
from subot.models import Quest
from subot.settings import Session


@ee.on(SaveUpdated.__name__)
def on_event_game_save(event: SaveUpdated):
    print(f"game saved: {event.save.story_quest()}")


@ee.on(QuestReceived.__name__)
def on_event_quest_received(event: QuestReceived):
    print(f"quest processed: {event.db_id}")
    with Session() as session:
        quest = session.query(Quest).filter(Quest.id == event.db_id).one()
        print(f"quest info: {quest=}")


def rewind(lines: list[str], save: Save) -> int:
    """Rewind log file state till reaching a point where state can be fully resumed
    Such as when entering the castle
    When first entering a realm
    when the game starts

    returns: index into `lines` of resumable state
    """

    mode = BotMode.UNDETERMINED
    rewind_idx = 0
    for rewind_idx, line in enumerate(reversed(lines), start=0):
        event = determine_event(line)
        if not event:
            continue
        if isinstance(event, GameStart):
            break
        elif isinstance(event, TeleportToRealm):
            mode = BotMode.REALM_LOADING

        elif isinstance(event, QuestReceivedRaw):
            # there will always be a realm quest. It is the 1st output during realm generation
            if mode is BotMode.REALM_LOADING:
                break

    return len(lines) - rewind_idx - 1


if __name__ == "__main__":
    import threading
    gotten_lines = queue.Queue()
    save = load_blank_save()
    game_state = GameState(save)
    su_log_thread = threading.Thread(daemon=True, target=tail_log_file, args=(gotten_lines,))
    su_log_thread.start()

    catch_up = True

    catchup_events: list[str] = []
    while True:
        try:
            line = gotten_lines.get(timeout=1/30)
            if catch_up:
                catchup_events.append(line)
                continue
            event = determine_event(line)
            if not event:
                continue
            # game_state.update(event)
        except queue.Empty:
            print("waiting for input")
            time.sleep(1/1000)
            break
    rewind_idx = rewind(catchup_events)
    print(f"{rewind_idx=}, {catchup_events[rewind_idx]}")

