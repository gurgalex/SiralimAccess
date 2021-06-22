import logging
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import cv2
import re
import numpy as np

import sqlalchemy
from numpy.typing import ArrayLike
from sqlalchemy.exc import NoResultFound

from subot.models import MasterNPCSprite, SpriteFrame, Session, AltarSprite, Realm, RealmLookup, ProjectItemSprite, \
    NPCSprite, FloorSprite, OverlaySprite

master_name_regex = re.compile(r"master_(?P<race>.*)_[\d].png")
realm_altar_regex = re.compile(r"spr_(?:altar|god)_(?P<realm>.*)_[\d].png")
project_item_regex = re.compile(r"project_(?P<name>.*)_[\d].png")
npc_regex = re.compile(r"npc_(?P<name>.*)_[\d].png")
custom_floortile_regex = re.compile(r"floortiles/(?P<realm>.*)/*.png")
overlay_sprite_regex = re.compile(r"(?P<realm>.*)_overlay_[\d].png")

MASTER_ICON_SIZE = 16
MASTER_NPC_SIZE = 32


def master_npcs(sprite_export_dir: Path, dest_dir: Path):
    master_sprites: dict[str, list] = defaultdict(list)

    for ct, master in enumerate(sprite_export_dir.glob("master_*.png")):
        img = cv2.imread(master.as_posix())
        height, width, _ = img.shape
        if height == MASTER_ICON_SIZE:
            continue
        master_race = master_name_regex.match(master.name)
        if not master_race:
            raise Exception(f"Regex did not find a master for file: {master}")

        master_race_filepart = (master_race.groups()[0])
        master_race_proper_name = f"{master_race_filepart.replace('_', ' ')} Master"

        master_sprites[master_race_proper_name].append(master)

        destination_file = dest_dir.joinpath(master.name)
        shutil.copy(master, destination_file)
        print(f"copied {ct} master frames")

    print(f"{len(master_sprites)} Masters")
    with Session() as session:
        for master_name, frames in master_sprites.items():
            sprite = MasterNPCSprite()
            sprite.long_name = master_name
            sprite.short_name = master_name

            frame: Path
            for frame in frames:
                new_path = Path("extracted_assets").joinpath(frame.name)
                sprite_frame = SpriteFrame()
                sprite_frame.filepath = new_path.as_posix()
                sprite.frames.append(sprite_frame)
            session.add(sprite)
        session.commit()




def altars(sprite_export_dir: Path, dest_dir: Path):
    @dataclass
    class AltarSpriteInsertInfo:
        file_paths: list[Path]
        realm: Realm

    generic_to_ingame_avatar_mapping = Realm.internal_realm_name_to_god_mapping

    altar_sprites: dict[str, AltarSpriteInsertInfo] = {}

    for ct, god_realm_altar_path in enumerate(sprite_export_dir.glob("spr_*.png")):
        altar_realm = realm_altar_regex.match(god_realm_altar_path.name)
        if not altar_realm:
            continue

        god_name: str = altar_realm.groups()[0]
        god_name_in_game: str = generic_to_ingame_avatar_mapping[god_name]
        altar_name_in_game: str = f"Realm Altar of {god_name_in_game}"

        realm_enum = Realm.god_to_realm_mapping.get(god_name_in_game)
        if realm_enum is None:
            logging.warning(f"realm altar {god_name_in_game} has no realm associated with it. file={god_realm_altar_path.as_posix()}")
            continue

        altar_info: AltarSpriteInsertInfo
        if altar_info := altar_sprites.get(altar_name_in_game):
            altar_info.file_paths.append(god_realm_altar_path)
        else:
            altar_info = AltarSpriteInsertInfo(realm=realm_enum, file_paths=[])
            altar_info.file_paths.append(god_realm_altar_path)
            altar_sprites[altar_name_in_game] = altar_info

        destination_file = dest_dir.joinpath(god_realm_altar_path.name)
        shutil.copy(god_realm_altar_path, destination_file)

    print(f"{len(altar_sprites)} realm altars")
    with Session() as session:
        existing_altar_sprites = session.query(AltarSprite).filter(AltarSprite.long_name.in_(altar_sprites.keys())).all()
        print(f"Found {len(existing_altar_sprites)} existing realm altars = {existing_altar_sprites=}")
        for altar_name, altar_info in altar_sprites.items():
            try:
                sprite = session.query(AltarSprite).filter_by(long_name=altar_name).one()
            except NoResultFound:
                sprite = AltarSprite()

            sprite.long_name = altar_name
            sprite.short_name = altar_name
            sprite.realm = session.query(RealmLookup).filter_by(enum=altar_info.realm).one()

            altar_info: AltarSpriteInsertInfo

            sprite.frames.clear()
            session.flush()
            for frame_path in altar_info.file_paths:
                new_path = Path("extracted_assets").joinpath(frame_path.name)
                sprite_frame = SpriteFrame()
                sprite_frame.filepath = new_path.as_posix()
                sprite.frames.append(sprite_frame)
            session.add(sprite)
            session.commit()


def insert_project_items(export_dir: Path, dest_dir: Path):

    sprites: dict[str, ProjectItemSprite] = {}

    for ct, project_item_path in enumerate(export_dir.glob("project_*.png")):
        sprite_frame_match = project_item_regex.match(project_item_path.name)
        if not sprite_frame_match:
            continue

        item_name_short: str = (sprite_frame_match.groups()[0])
        item_name_short: str = item_name_short.replace("_", " ")
        item_name_long: str = f"Project item {item_name_short}"

        destination_file = dest_dir.joinpath(project_item_path.name)
        shutil.copy(project_item_path, destination_file)

        sprites.setdefault(item_name_long, ProjectItemSprite(short_name=item_name_short, long_name=item_name_long))\
            .frames.append(SpriteFrame(_filepath=destination_file.as_posix()))

    print(f"{len(sprites)} project items")
    with Session() as session:
        for item_name_long, sprite in sprites.items():
            try:
                project_item = session.query(ProjectItemSprite).filter_by(long_name=item_name_long).one()
            except NoResultFound:
                project_item = sprite

            project_item.short_name = sprite.short_name
            project_item.long_name = sprite.long_name

            project_item.frames.clear()
            session.flush()

            frame: SpriteFrame
            for frame in sprite.frames:
                sprite_frame = SpriteFrame()
                sprite_frame.filepath = frame._filepath
                project_item.frames.append(sprite_frame)
            session.add(project_item)
            session.commit()


def npc(export_dir: Path, dest_dir: Path):
    sprite_and_frames: dict[str, list] = defaultdict(list)

    ct = 0
    for sprite_path in export_dir.glob("npc_*.png"):

        sprite_name = npc_regex.match(sprite_path.name)
        if not sprite_name:
            raise Exception(f"Regex did not find a match for NPC file: {sprite_path}")
        ct += 1
        sprite_name = (sprite_name.groups()[0])
        sprite_proper_name = f"{sprite_name.replace('_', ' ')}"

        sprite_and_frames[sprite_proper_name].append(sprite_path)

        destination_file = dest_dir.joinpath(sprite_path.name)
        shutil.copy(sprite_path, destination_file)
        print(f"copied {ct} NPC frames")

    print(f"{len(sprite_and_frames)} NPCs")
    with Session() as session:
        for short_name, frames in sprite_and_frames.items():
            long_name = f"NPC {short_name}"
            try:
                sprite = session.query(NPCSprite).filter_by(long_name=long_name).one()
            except NoResultFound:
                sprite = NPCSprite()

            sprite.long_name = long_name
            sprite.short_name = short_name

            sprite.frames.clear()
            session.flush()
            frame: Path
            for frame in frames:
                new_path = Path("extracted_assets").joinpath(frame.name)
                sprite_frame = SpriteFrame()
                sprite_frame.filepath = new_path.as_posix()
                sprite.frames.append(sprite_frame)
            session.add(sprite)
            session.commit()


def realm_floortiles(export_dir: Path, dest_dir: Path):
    tile_size = 32
    floortiles_path = export_dir.joinpath("bg_chaos_0.png")
    floortiles_img = cv2.imread(floortiles_path.as_posix(), cv2.IMREAD_UNCHANGED)

    row_to_realm_mapping = {
        0: Realm.GREAT_PANDEMONIUM,
        1: Realm.CAUSTIC_REACTOR,
        2: Realm.TEMPLE_OF_LIES,
        3: Realm.SANCTUM_UMBRA,
        4: Realm.TITAN_WOUND,
        5: Realm.BLOOD_GROVE,
        6: Realm.BASTION_OF_THE_VOID,
        7: Realm.AZURE_DREAM,
        8: Realm.CUTTHROAT_JUNGLE,
        9: Realm.ETERNITY_END,
        10: Realm.FARAWAY_ENCLAVE,
        11: Realm.KINGDOM_OF_HERETICS,
        12: Realm.FROSTBITE_CAVERNS,
        13: Realm.ARACHNID_NEST,
        14: Realm.THE_BARRENS,
        15: Realm.PATH_OF_THE_DAMNED,
        16: Realm.THE_SWAMPLANDS,
        17: Realm.REFUGE_OF_THE_MAGI,
        18: Realm.TORTURE_CHAMBER,
        19: Realm.UNSULLIED_MEADOWS,
        20: Realm.DEAD_SHIPS,
    }



    dest_dir_floortiles = dest_dir.joinpath("floortiles")
    dest_dir_floortiles.mkdir(exist_ok=True)

    floor_tiles: dict[str, FloorSprite] = {}

    for row_num, row in enumerate(range(0, floortiles_img.shape[0], tile_size)):

        tileset: list[tuple[ArrayLike, Path]] = []
        for col_num, column in enumerate(range(0, floortiles_img.shape[0], tile_size), start=1):
            img = floortiles_img[row:row + tile_size, column:column + tile_size]
            is_blank = np.count_nonzero(img) == 0
            if is_blank:
                continue

            if col_num == 1:
                tile_suffix = "_common"
            else:
                tile_suffix = ""
            realm_for_tile = row_to_realm_mapping[row_num]
            series_dir = Path(dest_dir_floortiles).joinpath(f"{realm_for_tile.name}")

            destination_filepath: Path = series_dir.joinpath(f"{row_num}-{col_num}{tile_suffix}.png")
            tileset.append((img, destination_filepath))

            sprite_name_short = "Floor"
            sprite_name = f"{realm_for_tile.value} Floor Tile"
            print(f"{sprite_name=}")

            floor_tiles.setdefault(sprite_name, FloorSprite(short_name=sprite_name_short, long_name=sprite_name,
                                                            realm=realm_for_tile))\
                .frames.append(SpriteFrame(_filepath=destination_filepath.as_posix()))

        is_blank_tileset = not tileset
        if is_blank_tileset:
            continue

        series_dir.mkdir(exist_ok=True)
        for tile in tileset:
            tile_data = tile[0]
            tile_filepath = tile[1]
            cv2.imwrite(tile_filepath.as_posix(), tile_data)


    # read floor tiles

    print([val.long_name for val in floor_tiles.values()])
    with Session() as session:
        for item_name_long, sprite in floor_tiles.items():
            try:
                floor_sprite = session.query(FloorSprite).filter_by(long_name=sprite.long_name).one()
            except NoResultFound:
                floor_sprite = sprite

            floor_sprite.short_name = sprite.short_name
            floor_sprite.long_name = sprite.long_name
            floor_sprite.realm_id = session.query(RealmLookup).filter_by(enum=sprite.realm).one().id
            print(floor_sprite.sprite_id, floor_sprite.long_name)

            floor_sprite.frames.clear()
            session.flush()

            frame: SpriteFrame
            for frame in sprite.frames:
                sprite_frame = SpriteFrame()
                sprite_frame.filepath = frame._filepath
                floor_sprite.frames.append(sprite_frame)
            session.add(floor_sprite)
            session.commit()

def add_overlay_tiles(export_dir: Path, dest_dir: Path):

    overlay_sprites: dict[str, OverlaySprite] = {}

    sprite_path: Path
    for sprite_path in export_dir.glob("*.png"):
        match = overlay_sprite_regex.match(sprite_path.name)
        if not match:
            continue
        print("got match for overlay", match.group(0))

        realm_name_internal: str = match.groups()[0]
        realm_in_game: Realm = Realm.generic_realm_name_to_ingame_realm(realm_name_internal)

        overlay_sprite = OverlaySprite()

        overlay_sprite.long_name = f"{realm_in_game.value} Overlay"
        overlay_sprite.short_name = overlay_sprite.long_name
        with Session() as session:
            overlay_sprite.realm_id = session.query(RealmLookup).filter_by(enum=realm_in_game).one().id

        sprite_frame = SpriteFrame()
        sprite_frame._filepath = Path("extracted_assets").joinpath(sprite_path.name).as_posix()
        overlay_sprites.setdefault(overlay_sprite.long_name, overlay_sprite).frames.append(sprite_frame)

        destination_file = dest_dir.joinpath(sprite_path.name)
        shutil.copy(sprite_path, destination_file)

    print(f"{len(overlay_sprites)} overlays found")
    with Session() as session:
        for sprite_name, sprite_new in overlay_sprites.items():
            try:
                sprite = session.query(OverlaySprite).filter_by(long_name=sprite_name).one()
                print(f"reusing overlay id={sprite.id}")
            except NoResultFound:
                print("noresultfuond")
                sprite = sprite_new
                session.add(sprite)
            sprite.long_name = sprite_name
            sprite.short_name = sprite_name
            sprite.realm_id = sprite_new.realm_id
            session.commit()

            sprite.frames.clear()
            session.flush()
            session.commit()

            sprite_id = sprite.id

            for frame in sprite_new.frames:
                new_frame = SpriteFrame(sprite_id=sprite_id, _filepath=frame._filepath)
                session.add(new_frame)
            session.commit()


if __name__ == "__main__":
    export_dir = Path("C:/Program Files (x86)/Steam/steamapps/common/Siralim Ultimate/Export_Textures_0.9.11/")
    dest_dir = Path("extracted_assets")
    try:
        master_npcs(export_dir, dest_dir=dest_dir)
    except sqlalchemy.exc.IntegrityError:
        logging.info("Reimporting or updating master sprites is not implemented")
    altars(export_dir, dest_dir)
    insert_project_items(export_dir, dest_dir)
    npc(export_dir, dest_dir)
    add_overlay_tiles(export_dir, dest_dir)
    realm_floortiles(export_dir, dest_dir)
