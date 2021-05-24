from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

import sqlalchemy
import toml
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from models import Sprite, SpriteType, SpriteFrame, Realm, QuestType, Quest, QuestAppearance, RealmLookup, \
    SpriteTypeLookup, AltarSprite


@dataclass(frozen=True)
class AssetConfig:
    config_data: dict
    toml_path: Path



if __name__ == "__main__":
    # an Engine, which the Session will use for connection
    # resources, typically in module scope
    engine = create_engine('sqlite:///assets.db', echo=True)

    # a sessionmaker(), also in the same scope as the engine
    Session = sessionmaker(engine)

    with Session() as session:
        for sprite_type in SpriteType:
            session.add(SpriteTypeLookup(name=sprite_type.name))
        try:
            session.commit()
        except IntegrityError as ie:
            session.rollback()

            print(f"unique constraint failed = {'UNIQUE' in ie.args[0]}")

    # populate realms
    with Session() as session:
        for realm in Realm:
            try:
                realm = RealmLookup(enum=realm, name=realm.value)
                session.add(realm)
                session.commit()
            except IntegrityError as ie:
                print(ie)
                session.rollback()


    tomls_location = "asset_tomls/"
    pngs_location = "assets_padded/"
    # pngs_location = "assets/"

    altars_list = []
    sprite_dict = defaultdict(list)
    for asset_path in Path(pngs_location).glob("**/**/**/*.png"):
        if "Temple Chest" in asset_path.stem:
            print(f"trying to insert temple chest: {asset_path}")
        sprite_name = asset_path.stem.split("-frame")[0]

        asset_config_path = Path(tomls_location).joinpath(asset_path.relative_to("assets_padded")).with_suffix(".png")
        try:
            toml_data = toml.load(asset_config_path)
        except FileNotFoundError as e:
            # populate default sprite metadata
            extracted_name = asset_config_path.stem.split("-")[0]
            toml_data = {
                "short_name": extracted_name,
                "long_name": extracted_name,
                "item_type": "generic",
                "is_quest_item": False,
                "is_floor_tile": False,
                "is_global_realm_item": False,
                "is_project_item": False,
            }
            print(f"toml not found - supplement data = {toml_data}")
        asset_config = AssetConfig(config_data=toml_data, toml_path=asset_config_path)
        sprite_dict[sprite_name].append(asset_config)
        if toml_data.get("item_type") == "Altar":
            altars_list.append(asset_config)
            print(f"caching altar for later use:{asset_config.config_data['long_name']}")

    asset_config_list: list[AssetConfig]
    for sprite_long_name, asset_config_list in sprite_dict.items():
        with Session() as session:
            first_frame = asset_config_list[0]
            if first_frame.config_data.get("item_type") == "Altar":
                print(f"Found altar: {first_frame.config_data}")

            sprite = Sprite(short_name=first_frame.config_data["short_name"],
                            long_name=first_frame.config_data["long_name"],
                            )
            sprite.type_id = session.query(SpriteTypeLookup).filter_by(name=SpriteType.DECORATION).first().id
            realm_name: str
            if realm_name := first_frame.config_data.get("realm"):
                realm_name_sanitized = realm_name.replace("'s", "").replace(" ", "_")
                realm_name_sanitized = realm_name_sanitized.upper()
                realm_enum = Realm[realm_name_sanitized]

                # add sprite to realm
                realm = session.query(RealmLookup).filter_by(enum=realm_enum).first()
                realm.sprites.append(sprite)

            if item_type := first_frame.config_data.get('item_type'):
                if item_type == "Altar":
                    altar_sprite = AltarSprite()
                    altar_sprite.sprite = sprite
                    realm = session.query(RealmLookup).filter_by(name=first_frame.config_data["realm"]).first()
                    assert realm is not None
                    altar_sprite.realm = realm
                    session.add(altar_sprite)


            for frame in asset_config_list:
                png_path = Path(pngs_location).joinpath(frame.toml_path.relative_to("asset_tomls")).with_suffix(".png")
                if not png_path.exists():
                    print(f"missing png path: {png_path.as_posix()}")
                    continue
                sprite_frame = SpriteFrame()
                sprite_frame.filepath = png_path.as_posix()
                sprite.frames.append(sprite_frame)
                session.add(sprite)
            try:
                session.commit()
            except IntegrityError as ie:
                print(f"unique contraint violation")


