from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy import ForeignKey, String, Integer, Column, create_engine, Table
import sqlalchemy as db
import enum

from sqlalchemy.engine import Engine
from sqlalchemy import event
from subot.settings import DATABASE_CONFIG, IMAGE_PATH

Base = declarative_base()

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class SpriteFrame(Base):
    __tablename__ = "sprite_frame"
    id = Column(Integer, primary_key=True, nullable=False)
    sprite_id = Column(Integer, ForeignKey('sprite.id'), nullable=False)
    meta_extra = Column(String, nullable=True)
    _filepath = Column('filepath', String, nullable=False, unique=True)

    @hybrid_property
    def filepath(self):
        new_image_path = IMAGE_PATH.joinpath(self._filepath)
        return new_image_path.as_posix()



class SpriteType(enum.Enum):
    """How is the sprite commonly used in the game"""
    # all sprites in the game that could be inspected
    CREATURE = "creature"
    # A catch-all for every other graphic asset in the game
    DECORATION = "decoration"
    ENEMY = "enemy"
    # Costume the player can wear
    WARDROBE = "wardrobe"


class SpriteTypeLookup(Base):
    __tablename__ = 'sprite_type'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(db.Enum(SpriteType), unique=True, nullable=False)


class Sprite(Base):
    """A collection of sprite frames for a particular game graphic asset
    Assumptions
    1. No tw2 sprites will share the same long_name
    2. The frames of each sprite share the same collision area
    """
    __tablename__ = "sprite"
    id = Column(Integer, primary_key=True, nullable=False)
    short_name = Column(String, nullable=False)
    long_name = Column(String, nullable=False, unique=True)
    # todo: today: add relationship for RealmSprite table

    type_id = Column(Integer, ForeignKey('sprite_type.id'))
    type = relationship('SpriteTypeLookup', backref='sprites', uselist=False)
    frames = relationship("SpriteFrame", backref="sprite", lazy='joined')


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

class Realm(enum.Enum):
    UNSULLIED_MEADOWS = 'Unsullied Meadows'
    BLOOD_GROVE = 'Blood Grove'
    TEMPLE_OF_LIES = 'Temple of Lies'
    FROSTBITE_CAVERNS = 'Frostbite Caverns'
    PATH_OF_THE_DAMNED = 'Path of the Damned'
    DEAD_SHIPS = 'Dead Ships'
    KINGDOM_OF_HERETICS = 'Kingdom of Heretics'
    FARAWAY_ENCLAVE = 'Faraway Enclave'
    THE_SWAMPLANDS = 'The Swamplands'
    TITAN_WOUND = "Titan's Wound"
    SANCTUM_UMBRA = 'Sanctum Umbra'
    ARACHNID_NEST = 'Arachnid Nest'
    AZURE_DREAM = 'Azure Dream'
    TORTURE_CHAMBER = 'Torture Chamber'
    BASTION_OF_THE_VOID = 'Bastion of the Void'
    CUTTHROAT_JUNGLE = 'Cutthroat Jungle'
    CAUSTIC_REACTOR = 'Caustic Reactor'
    ETERNITY_END = "Eternity's End"
    GREAT_PANDEMONIUM = 'Great Pandemonium'
    THE_BARRENS = 'The Barrens'
    REFUGE_OF_THE_MAGI = 'Refuge of the Magi'


class RealmLookup(Base):
    __tablename__ = 'realm'
    id = Column(Integer, primary_key=True, nullable=False)
    enum = Column(db.Enum(Realm, name="enum_realm"), nullable=False, unique=True, index=True)
    name = Column(String, nullable=False, unique=True,index=True)

    god_altar_sprite = relationship("Sprite", secondary="altar_sprite", uselist=False)
    sprites = relationship("Sprite", secondary="realm_sprite", uselist=True, backref='realm')


class AltarSprite(Base):
    __tablename__ = 'altar_sprite'
    sprite_id = Column(Integer, ForeignKey('sprite.id'), unique=True, primary_key=True)
    realm_id = Column(Integer, ForeignKey('realm.id'), unique=True, primary_key=True)

    sprite = relationship('Sprite', uselist=False, viewonly=True)
    realm = relationship('RealmLookup', uselist=False, viewonly=True)


class RealmSprite(Base):
    __tablename__ = 'realm_sprite'
    realm_id = Column(Integer, ForeignKey('realm.id'), nullable=False, primary_key=True)
    sprite_id = Column(Integer, ForeignKey('sprite.id'), nullable=False, primary_key=True, unique=True)


class ProjectType(enum.Enum):

    MISSION = "mission"
    SPECIAL_PROJECT = "special_project"



class Project(Base):
    """Info about a project, projects are started by talking to the NPC named Everett

    model assumptions
    * A Project has 1+ project item
    * Each project has a unique name
    * A project item optionally has a sprite associated with it



    """
    __tablename__ = "project"
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String, unique=True, nullable=False, index=True)
    type = Column(db.Enum(ProjectType), nullable=False)


class Quest(Base):
    """Info about how to complete the quest

    model assumptions
    * Each quest has a unique title
    * A quest will either have the requirement be unique to the realm, OR it will be available in all realms
    """
    __tablename__ = 'quest'
    id = Column(Integer, primary_key=True, nullable=False)
    title = Column(String, nullable=False, unique=True, index=True)
    quest_type = Column(db.Enum(QuestType, name="enum_quest_type"), nullable=False)

    # What realm the quest is tied to. Null if non-specific
    specific_realm = Column(String, ForeignKey('realm.id'), nullable=True)

    sprites = relationship('Sprite', secondary="quest_sprite", uselist=True, lazy='joined', doc="returns 0 or more sprites associated with a realm quest")

    def __repr__(self):
        return f"Quest({self.id=}, {self.title=}, {self.quest_type=}, {self.specific_realm=}, {self.sprites=}"


class QuestSprite(Base):
    __tablename__ = 'quest_sprite'
    quest_id = Column(ForeignKey('quest.id'), primary_key=True, nullable=False)
    sprite_id = Column(ForeignKey('sprite.id'), primary_key=True, nullable=False)


debug = False
engine = create_engine(DATABASE_CONFIG.uri, echo=debug)
Session = sessionmaker(engine)

if __name__ == "__main__":
    engine = create_engine(DATABASE_CONFIG.uri, echo=True)
    Base.metadata.create_all(engine)