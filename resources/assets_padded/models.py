from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import ForeignKey, String, Integer, Column, create_engine, Table
import sqlalchemy as db
import enum

from sqlalchemy.engine import Engine
from sqlalchemy import event

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine = create_engine('sqlite:///assets.db', echo=True)
Base = declarative_base()


class SpriteFrame(Base):
    __tablename__ = "sprite_frame"
    sprite = Column(Integer, ForeignKey('sprite.id'), primary_key=True,nullable=False)
    frame_number = Column(Integer, primary_key=True, nullable=False)
    filepath = Column(String, nullable=False, unique=True)


class Sprite(Base):
    """A collection of sprite frames for a particular game graphic asset
    Assumptions
    1. No 2 sprites will share the same long_name
    2. The frames of each sprite share the same collision area
    """
    __tablename__ = "sprite"
    id = Column(Integer, primary_key=True, nullable=False)
    short_name = Column(String, nullable=False)
    long_name = Column(String, nullable=False, unique=True)
    frames = relationship("SpriteFrame", backref="sprite")
    # Todo: Add collision rect in tiles from top-left (x, y, w, h)


class QuestType(enum.Enum):
    """What type of object is the quest looking for"""
    # Just asks to collect a set of decorations in any order
    decoration = "decoration"
    enemy = "normal enemy"
    nemesis = "nemesis"
    rescue = "rescue"
    false_god = "false god"
    nether_boss = "nether boss"


class QuestAppearance(enum.Enum):
    single_realm = 1
    all_realm = 2
    castle = 3


class Realm(Base):
    __tablename__ = 'realm'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String, nullable=False, unique=True)
    god_altar_id = Column(Integer, ForeignKey('sprite.id'), nullable=False, unique=True)
    god_altar = relationship("sprite", backref="for_realm")


class Quest(Base):
    """Info about how to complete the quest"""
    __tablename__ = 'quest'
    id = Column(Integer, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    quest_type = Column(db.Enum(QuestType, name="enum_quest_type"), nullable=False)

    # Is this quest always for a specific realm
    specific_realm = Column(String, ForeignKey('realm.id'), nullable=True)


Base.metadata.create_all(engine)