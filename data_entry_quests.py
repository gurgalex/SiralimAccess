import argparse
import sys
from pathlib import Path
from typing import Optional

import subot
from subot.models import Quest, QuestAppearance, QuestType, QuestSprite, Sprite, Realm, RealmLookup, SpriteType, \
    SpriteFrame, SpriteTypeLookup, FloorSprite
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from subot.settings import DATABASE_CONFIG


import click

engine = create_engine(DATABASE_CONFIG.uri, echo=True)
Session = sessionmaker(engine)

@click.group()
def cli():
    pass

    # add_quest_parser = Cmd2ArgumentParser()
    # add_quest_parser.add_argument("--title", help="Bolded title of quest", required=True)
    # add_quest_parser.add_argument("--sprites-long-name", required=True,  help="Comma separated list of the 'long_name' of each sprite for a quest in the DB")
    # add_quest_parser.add_argument("--quest_type", default=QuestType.decoration, choices=[quest_type.name for quest_type in QuestType])
    # add_quest_parser.add_argument("--specific_realm", required=False, choices=[realm.name for realm in Realm])

@click.command()
@click.argument("title")
@click.option("--sprites-long-name", help="Comma separated list of the 'long_name' of each sprite for a quest in the DB")
@click.option("--quest-type", default=QuestType.decoration, type=click.Choice(choices=[quest_type.name for quest_type in QuestType]))
@click.option("--specific-realm", type=click.Choice(choices=[realm.name for realm in Realm]))
def add_quest(title: str, sprites_long_name: str, quest_type: Optional[str], specific_realm: Optional[str]):
    with Session() as session:

        quest = Quest(title=title)
        if (realm_enum := specific_realm) is not None:
            realm = session.query(RealmLookup).filter_by(enum=Realm[realm_enum]).first()
            if realm is None:
                raise Exception(f"No realm was returned for {realm_enum=}")
            quest.specific_realm = realm
        quest_type = QuestType[quest_type]
        quest.quest_type = quest_type

        if sprites_long_name:
            for sprite_name in sprites_long_name.split(","):
                sprite = session.query(Sprite).filter_by(long_name=sprite_name).first()
                if sprite is None:
                    raise Exception(f"sprite long name `{sprite_name}` could not be found in the database")
                quest.sprites.append(sprite)
        click.echo(f"entered Quest info: {quest=}")
        session.add(quest)
        session.commit()
        click.echo(f"Saved Quest: {title}\n")

@click.command()
@click.argument("long-name", required=True)
@click.argument("sprite-folder", required=True, type=click.Path(file_okay=False, resolve_path=True))
@click.option("--short-name", required=False, help="Short name to use instead of the long name in TTS output")
@click.option("--type", default=SpriteType.DECORATION.name, type=click.Choice(choices=[sprite_type.name for sprite_type in SpriteType]))
@click.option("--specific-realm", type=click.Choice(choices=[realm.name for realm in Realm]))
def add_sprite(short_name: Optional[str], long_name: str, type: str, sprite_folder: str, specific_realm: Optional[str]):
    sprite_folder = Path(sprite_folder)
    new_sprite_type: SpriteType = SpriteType[type]
    with Session() as session:
        sprite_type = session.query(SpriteTypeLookup).filter_by(name=type).one()

        sprite = Sprite.detetermine_child_class(new_sprite_type)()
        print(f"determined sprite type: {sprite=}")

        sprite.long_name = long_name
        if not short_name:
            sprite.short_name = long_name
        else:
            sprite.short_name = short_name

        if (realm_enum := specific_realm) is not None:
            realm = session.query(RealmLookup).filter_by(enum=Realm[realm_enum]).first()
            if realm is None:
                raise Exception(f"No realm was returned for {realm_enum=}")
            sprite.realm_id = realm.id

        maybe_sprite_folder = sprite_folder
        if not maybe_sprite_folder.is_dir():
            raise ValueError(f"supplied sprite folder {maybe_sprite_folder.as_posix()} is not a directory")
        try:
            maybe_sprite_folder = maybe_sprite_folder.relative_to(subot.settings.IMAGE_PATH)
        except ValueError:
            raise ValueError(f"supplied sprite folder {maybe_sprite_folder.as_posix()} is not relative to {subot.settings.IMAGE_PATH.as_posix()}")
        sprite_folder = maybe_sprite_folder

        print(f"{sprite_folder=}")
        for frame_path in sprite_folder.glob("*.png"):
            filepath = frame_path.as_posix()
            sprite_frame = SpriteFrame()
            sprite_frame.filepath = filepath
            sprite.frames.append(sprite_frame)

        click.echo(f"entered Sprite info: {sprite.short_name}\n {sprite.long_name}\n{sprite.type=}\n{sprite.frames=}\n")
        session.add(sprite)
        session.commit()
    click.echo(f"Added new Sprite: {long_name}")


# def replace_subclass_sprite_entry(old_type_id: SpriteType, new_type_id: SpriteType, sprite_id: int, session):
#     if old_type_id is SpriteType.DECORATION:
#         # don't delete parent
#         return
#
#     old_subclass = Sprite.__mapper__.polymorphic_map[old_type_id.value].class_
#     session.query(old_subclass).filter_by(sprite_id=sprite_id).delete()
#
#     new_subclass = Sprite.__mapper__.polymorphic_map[old_type_id.value].class_(sprite_id=sprite_id)
#     new_subclass.type_id = new_sprite_type.value
#
#     session.add(new_subclass)



@click.command()
@click.argument("old-long-name", required=True)
@click.argument("sprite-folder", required=True, type=click.Path(file_okay=False, resolve_path=True))
@click.option("--short-name", required=False, help="Short name to use instead of the long name in TTS output")
@click.option("--new-long-name", required=False, help="New long name to use")
@click.option("--sprite-type", type=click.Choice(choices=[sprite_type.name for sprite_type in SpriteType]))
def update_sprite(old_long_name: str, short_name: Optional[str], new_long_name: str, sprite_type: str, sprite_folder: str):
    sprite_folder = Path(sprite_folder)
    if sprite_type:
        raise NotImplementedError("Changing the type of the sprite is not supported yet")

    with Session.begin() as session:

        sprite = session.query(Sprite).filter_by(long_name=old_long_name).one()

        # delete existing sprite frames
        session.query(SpriteFrame).filter(sprite.id == SpriteFrame.sprite_id).delete()
        session.expire_all()

        click.echo(
            f"Deleted frames for Sprite: {sprite.long_name}\n")

        if short_name:
            sprite.short_name = short_name
        if new_long_name:
            sprite.long_name = new_long_name

        maybe_sprite_folder = sprite_folder
        if not maybe_sprite_folder.is_dir():
            raise ValueError(f"supplied sprite folder {maybe_sprite_folder.as_posix()} is not a directory")
        try:
            maybe_sprite_folder = maybe_sprite_folder.relative_to(subot.settings.IMAGE_PATH)
        except ValueError:
            raise ValueError(f"Supplied sprite folder {maybe_sprite_folder.as_posix()} is not relative to {subot.settings.IMAGE_PATH.as_posix()}")
        sprite_folder = maybe_sprite_folder

        print(f"{sprite_folder=}")
        for frame_path in sprite_folder.glob("*.png"):
            filepath = frame_path.as_posix()
            sprite_frame = SpriteFrame()
            sprite_frame.filepath = filepath
            sprite.frames.append(sprite_frame)

        click.echo(f"entered Sprite info: {sprite.short_name}\n {sprite.long_name}\n{sprite.type=}\n{sprite.frames=}\n")
        session.add(sprite)
        click.echo(f"Updated Sprite: {sprite.long_name}")


cli.add_command(add_sprite)
cli.add_command(add_quest)
cli.add_command(update_sprite)
if __name__ == "__main__":
    cli()
