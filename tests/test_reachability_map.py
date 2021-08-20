import pytest

from subot.pathfinder.map import Map, TileType, Color

def test_single_black_tile_is_reachable():
    arr = [
        "UUUBB",
        "UUUUB",
        "UUPUU",
        "UUUUU",
        "UUUUU",
    ]

    sol_array = [
        "UUURB",
        "UUUUR",
        "UUPUU",
        "UUUUU",
        "UUUUU",
    ]

    map = Map.from_ascii(arr)
    map.find_reachable_blocks()
    assert map.to_ascii() == sol_array


def test_black_tile_is_not_reachable_from_wall():
    arr = [
        "BWUUU",
        "WUUUU",
        "UUPUU",
        "UUUUU",
        "UUUUB",
    ]

    sol_array = [
        "BWUUU",
        "WUUUU",
        "UUPUU",
        "UUUUU",
        "UUUUR",
    ]

    map = Map.from_ascii(arr)
    map.find_reachable_blocks()
    assert map.to_ascii() == sol_array





def test_wall_tiles_are_not_traversable():
    arr = [
        "BWUFB",
        "WUUFW",
        "UFPFU",
        "UFWWW",
        "BFFFB",
    ]

    sol_array = [
        "BWUFR",
        "WUUFW",
        "UFPFU",
        "UFWWW",
        "RFFFR",
    ]

    map = Map.from_ascii(arr)
    map.find_reachable_blocks()
    assert map.to_ascii() == sol_array


def test_unfilled_tiles_are_not_paths():
    arr = [
        "B..FB",
        "UF..F",
        ".FP..",
        "U....",
        "BUUUU",
    ]

    sol_array = [
        "R..FB",
        "UF..F",
        ".FP..",
        "U....",
        "BUUUU",
    ]

    map = Map.from_ascii(arr)
    map.find_reachable_blocks()
    assert map.to_ascii() == sol_array
