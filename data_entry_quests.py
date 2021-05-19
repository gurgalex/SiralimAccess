import argparse
import sys

from models import Quest, QuestAppearance, QuestType, QuestSprite, Sprite, Realm, RealmLookup
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from settings import DATABASE_CONFIG
import cmd2


class DataEntryManagerCmdLine(cmd2.Cmd):
    """Add new data to the database"""
    def __init__(self):
        super().__init__()
        engine = create_engine(DATABASE_CONFIG.uri)
        self.Session = sessionmaker(engine)

    add_quest_parser = cmd2.Cmd2ArgumentParser()
    add_quest_parser.add_argument("--title", help="Bolded title of quest", required=True)
    add_quest_parser.add_argument("--sprites-long-name", required=True,  help="Comma separated list of the 'long_name' of each sprite for a quest in the DB")
    add_quest_parser.add_argument("--quest_type", default=QuestType.decoration, choices=[quest_type.name for quest_type in QuestType])
    add_quest_parser.add_argument("--specific_realm", required=False, choices=[realm.name for realm in Realm])

    @cmd2.with_argparser(add_quest_parser)
    def do_add_quest(self, args: argparse.Namespace) -> None:
        with self.Session() as session:

            quest = Quest(title=args.title)
            if realm_enum := args.specific_realm is not None:
                realm = session.query(RealmLookup).filter_by(enum=Realm[realm_enum]).first()
                if realm is None:
                    raise Exception(f"No realm was returend for {realm_enum=}")
                quest.specific_realm = realm
            quest_type = QuestType[args.quest_type.name]
            quest.quest_type = quest_type

            if args.sprites_long_name is not None or args.sprites_long_name != "":
                for sprite_name in args.sprites_long_name.split(","):
                    sprite = session.query(Sprite).filter_by(long_name=sprite_name).first()
                    if sprite is None:
                        raise Exception(f"sprite long name `{sprite_name}` could not be found in the database")
                    quest.sprites.append(sprite)
            session.add(quest)
            session.commit()



        self.poutput(f"enter Quest info: {args.title=}\n {args.sprites_long_name=}\n{args.quest_type=}\n")




if __name__ == "__main__":

    app = DataEntryManagerCmdLine()
    sys.exit(app.cmdloop())






