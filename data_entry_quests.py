import argparse
import sys
from pathlib import Path
from typing import Optional

import subot
from subot.models import Quest, QuestAppearance, QuestType, QuestSprite, Sprite, Realm, RealmLookup, SpriteType, \
    SpriteFrame, SpriteTypeLookup
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
        if realm_enum := specific_realm is not None:
            realm = session.query(RealmLookup).filter_by(enum=Realm[realm_enum]).first()
            if realm is None:
                raise Exception(f"No realm was returend for {realm_enum=}")
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
@click.option("--short-name", required=False, help="Short name to use instead of the long name in TTS output")
@click.argument("long-name", required=True)
@click.option("--type", default=SpriteType.DECORATION.name, type=click.Choice(choices=[sprite_type.name for sprite_type in SpriteType]))
@click.argument("sprite-folder", required=True, type=click.Path(file_okay=False, resolve_path=True))
def add_sprite(short_name: Optional[str], long_name: str, type: str, sprite_folder: str):
    sprite_folder = Path(sprite_folder)
    with Session() as session:
        sprite_type = session.query(SpriteTypeLookup).filter_by(name=type).one()

        sprite = Sprite()
        sprite.long_name = long_name
        if not short_name:
            sprite.short_name = long_name
        else:
            sprite.short_name = short_name
        sprite.type = sprite_type

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


# class DataEntryManagerCmdLine():
#     """Add new data to the database"""
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#
#
#     add_quest_parser = Cmd2ArgumentParser()
#     add_quest_parser.add_argument("--title", help="Bolded title of quest", required=True)
#     add_quest_parser.add_argument("--sprites-long-name", required=True,  help="Comma separated list of the 'long_name' of each sprite for a quest in the DB")
#     add_quest_parser.add_argument("--quest_type", default=QuestType.decoration, choices=[quest_type.name for quest_type in QuestType])
#     add_quest_parser.add_argument("--specific_realm", required=False, choices=[realm.name for realm in Realm])
#
#
#
#     @cmd2.with_argparser(add_quest_parser)
#     def do_add_quest(self, args: argparse.Namespace) -> None:
#         with self.Session() as session:
#
#             quest = Quest(title=args.title)
#             if realm_enum := args.specific_realm is not None:
#                 realm = session.query(RealmLookup).filter_by(enum=Realm[realm_enum]).first()
#                 if realm is None:
#                     raise Exception(f"No realm was returend for {realm_enum=}")
#                 quest.specific_realm = realm
#             quest_type = QuestType[args.quest_type.name]
#             quest.quest_type = quest_type
#
#             if args.sprites_long_name is not None or args.sprites_long_name != "":
#                 for sprite_name in args.sprites_long_name.split(","):
#                     sprite = session.query(Sprite).filter_by(long_name=sprite_name).first()
#                     if sprite is None:
#                         raise Exception(f"sprite long name `{sprite_name}` could not be found in the database")
#                     quest.sprites.append(sprite)
#             session.add(quest)
#             session.commit()
#
#         self.poutput(f"entered Quest info: {args.title=}\n {args.sprites_long_name=}\n{args.quest_type=}\n")


cli.add_command(add_sprite)
cli.add_command(add_quest)

if __name__ == "__main__":
    cli()





