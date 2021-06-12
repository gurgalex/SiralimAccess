import shutil
from collections import defaultdict
from pathlib import Path
import cv2
import re

from subot.models import MasterNPCSprite, SpriteFrame, Session

master_name_regex = re.compile("master_(.*)_[0-9].png")

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


if __name__ == "__main__":
    export_dir = Path("C:/Program Files (x86)/Steam/steamapps/common/Siralim Ultimate/Export_Textures_0.9.11/")
    dest_dir = Path("extracted_assets")
    master_npcs(export_dir, dest_dir=dest_dir)
