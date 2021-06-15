import logging
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import cv2
import re

import sqlalchemy
from sqlalchemy.exc import NoResultFound

from subot.models import MasterNPCSprite, SpriteFrame, Session, AltarSprite, Realm, RealmLookup

master_name_regex = re.compile(r"master_(?P<race>.*)_[\d].png")
realm_altar_regex = re.compile(r"spr_(?:altar|god)_(?P<realm>.*)_[\d].png")

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


god_to_realm_mapping = {
    "Aeolian": Realm.UNSULLIED_MEADOWS,
    "Apocranox": Realm.BLOOD_GROVE,
    "Aurum": Realm.TEMPLE_OF_LIES,
    "Azural": Realm.FROSTBITE_CAVERNS,
    "Erebyss": Realm.PATH_OF_THE_DAMNED,
    "Friden": Realm.DEAD_SHIPS,
    "Gonfurian": Realm.KINGDOM_OF_HERETICS,
    "Lister": Realm.FARAWAY_ENCLAVE,
    "Meraxis": Realm.THE_SWAMPLANDS,
    "Mortem": Realm.TITAN_WOUND,
    "Perdition": Realm.SANCTUM_UMBRA,
    "Regalis": Realm.ARACHNID_NEST,
    "Surathli": Realm.AZURE_DREAM,
    "Tartarith": Realm.TORTURE_CHAMBER,
    "Tenebris": Realm.BASTION_OF_THE_VOID,
    "Torun": Realm.CUTTHROAT_JUNGLE,
    "Venedon": Realm.CAUSTIC_REACTOR,
    "Vertraag": Realm.ETERNITY_END,
    "Vulcanar": Realm.GREAT_PANDEMONIUM,
    "Yseros": Realm.THE_BARRENS,
    "Zonte": Realm.REFUGE_OF_THE_MAGI,
}


def altars(sprite_export_dir: Path, dest_dir: Path):
    @dataclass
    class AltarSpriteInsertInfo:
        file_paths: list[Path]
        realm: Realm

    generic_to_ingame_avatar_mapping = {
        "cave": "Regalis",
        "death": "Erebyss",
        "chaos": "Vulcanar",
        "desert": "Yseros",
        "dungeon": "Tartarith",
        "haunted": "Gonfurian",
        "grassland": "Aeolian",
        "island": "Lister",
        "jungle": "Torun",
        "life": "Surathli",
        "nature": "Meraxis",
        "underwater": "Friden",
        "snow": "Azural",
        "sorcery": "Zonte",
        "space": "Vertraag",

        "apocranox": "Apocranox",
        "aurum": "Aurum",
        "caliban": "Caliban",
        "mortem": "Mortem",
        "perdition": "Perdition",
        "tenebris": "Tenebris",
        "venedon": "Venedon",
    }


    altar_sprites: dict[str, AltarSpriteInsertInfo] = {}

    for ct, god_realm_altar_path in enumerate(sprite_export_dir.glob("spr_*.png")):
        altar_realm = realm_altar_regex.match(god_realm_altar_path.name)
        if not altar_realm:
            continue

        god_name: str = (altar_realm.groups()[0])
        god_name_in_game: str = generic_to_ingame_avatar_mapping[god_name]
        altar_name_in_game: str = f"Realm Altar of {god_name_in_game}"

        realm_enum = god_to_realm_mapping.get(god_name_in_game)
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


if __name__ == "__main__":
    export_dir = Path("C:/Program Files (x86)/Steam/steamapps/common/Siralim Ultimate/Export_Textures_0.9.11/")
    dest_dir = Path("extracted_assets")
    try:
        master_npcs(export_dir, dest_dir=dest_dir)
    except sqlalchemy.exc.IntegrityError:
        logging.info("Reimporting or updating master sprites is not implemented")
    altars(export_dir, dest_dir)
