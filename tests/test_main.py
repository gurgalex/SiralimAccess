import pytest
from subot.main import Bot
from subot.datatypes import Rect
from subot.utils import Point

TILE_SIZE = 32

def test_near_player_grid_calc_clips_to_full_tiles():
    nearby_tiles = 7
    near_tiles_rect = Rect(x=235, y=219, w=TILE_SIZE*nearby_tiles, h=TILE_SIZE*nearby_tiles)
    y_offset = 8
    x_offset = 0
    aligned_floor_tile_rect = Rect(x=x_offset, y=y_offset, w=TILE_SIZE, h=TILE_SIZE)

    top_left_tile_pt = Bot.top_left_tile(aligned_floor_tile=aligned_floor_tile_rect, client_rect=near_tiles_rect)
    bottom_right_tile_pt = Bot.bottom_right_tile(aligned_floor_tile_rect, client_rect=near_tiles_rect)
    nearest_grid = Bot.compute_grid_rect(top_left_tile=top_left_tile_pt, bottom_right_tile=bottom_right_tile_pt)

    top_left_tile_pt_answer = Point(x=x_offset, y=y_offset)
    bottom_right_tile_pt_answer = Point(x=192, y=168)
    window_grid_rect_answer = Rect(x=x_offset, y=y_offset, w=224, h=192)

    assert top_left_tile_pt == top_left_tile_pt_answer
    assert bottom_right_tile_pt == bottom_right_tile_pt_answer
    assert nearest_grid == window_grid_rect_answer


def test_full_grid_calc_clips_to_full_tiles():
    y_offset = 8
    x_offset = 0

    su_window_rect = Rect(x=235, y=219, w=1280, h=720)
    aligned_floor_tile_rect = Rect(x=576, y=y_offset, w=32, h=32)

    top_left_tile_pt = Bot.top_left_tile(aligned_floor_tile=aligned_floor_tile_rect, client_rect=su_window_rect)
    bottom_right_tile_pt = Bot.bottom_right_tile(aligned_floor_tile_rect, client_rect=su_window_rect)
    window_grid = Bot.compute_grid_rect(top_left_tile=top_left_tile_pt, bottom_right_tile=bottom_right_tile_pt)

    # nearest whole tile 8 pixels from top of area
    top_left_tile_pt_answer = Point(x=x_offset, y=y_offset)
    bottom_right_tile_pt_answer = Point(x=1248, y=680)
    window_grid_rect_answer = Rect(x=x_offset, y=y_offset, w=1280, h=704)

    print(top_left_tile_pt == top_left_tile_pt_answer)
    print(bottom_right_tile_pt == bottom_right_tile_pt_answer)
    assert window_grid == window_grid_rect_answer


