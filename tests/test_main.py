import pytest
from subot.main import Bot, Rect, Point

TILE_SIZE = 32

def test_nearby_grid_calc_is_correct():

    nearby_screenshot_rect = Rect(x=383, y=146, w=224, h=224)
    aligned_floor_tile_rect = Rect(x=383, y=154, w=TILE_SIZE, h=TILE_SIZE)

    top_left_tile_pt = Bot.top_left_tile(aligned_floor_tile_rect=aligned_floor_tile_rect, area_rect=nearby_screenshot_rect)
    bottom_right_tile_pt = Bot.bottom_right_tile(aligned_floor_tile_rect, client_rect=nearby_screenshot_rect)
    nearby_grid_rect = Bot.compute_grid_rect(top_left_pt=top_left_tile_pt, bottom_right_pt=bottom_right_tile_pt)

    # nearest whole tile 8 pixels from top of area
    top_left_tile_pt_answer = Point(x=383, y=154)
    bottom_right_tile_pt_answer = Point(x=575, y=314)

    nearby_grid_rect_answer = Rect(x=607, y=346, w=224, h=192)

    assert top_left_tile_pt == top_left_tile_pt_answer
    assert bottom_right_tile_pt == bottom_right_tile_pt_answer
    assert nearby_grid_rect == nearby_grid_rect_answer


