from __future__ import annotations
from functools import cache

import cv2
from numpy.typing import ArrayLike
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import ForeignKey, String, Integer, Column, create_engine, Boolean
import sqlalchemy as db
import enum
from enum import auto

from sqlalchemy.engine import Engine
from sqlalchemy import event
from subot.settings import DATABASE_CONFIG, IMAGE_PATH, engine

Base = declarative_base()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


class SpriteType(enum.Enum):
    """How is the sprite commonly used in the game"""
    # all sprites in the game that could be inspected
    CREATURE = 1
    # A catch-all for every other graphic asset in the game
    DECORATION = 2
    ENEMY = 3
    # Decoration that only appears in the castle
    CASTLE_DECORATION = 4
    NPC = 5
    FLOOR = 6
    ALTAR = 7
    # Sprite of each creature race's master
    MASTER_NPC = 8
    # Sprite for an item of a project
    PROJ_ITEM = 9

    # sprite used to overlay onto a rendered realm (rare)
    OVERLAY = 10
    RESOURCE_NODE = 11
    WALL = 12
    CHEST = 13

    TELEPORTATION_SHRINE = 14
    TREASURE_MAP = 15
    DIVINATION_CANDLE = 16
    EMBLEM = 17
    BREAKABLE = 18
    LARGE_CHEST = 19
    DEMONIC_STATUE = 20
    BIG_CANDLE = 21
    LARGE_CHEST_KEY = 22
    MATERIALS_COMMON = 23
    MATERIALS_RARE = 24
    MATERIALS_LEGENDARY = 25
    SPELL_MATERIAL_BAG = 26
    # portal belonging ot each realm. Enter to find a random creature + 2 treasure chests
    REALM_PORTAL = 27




@cache
def read_data_color(filepath: str) -> ArrayLike:
    return cv2.imread(filepath, cv2.IMREAD_UNCHANGED)


@cache
def read_data_gray(filepath: str) -> ArrayLike:
    img_color = read_data_color(filepath)
    return cv2.cvtColor(img_color, cv2.COLOR_BGRA2GRAY)


class SpriteFrame(Base):
    __tablename__ = "sprite_frame"
    id = Column(Integer, primary_key=True, nullable=False)
    sprite_id = Column(Integer, ForeignKey('sprite.id'), nullable=False)
    meta_extra = Column(String, nullable=True)
    _filepath = Column('filepath', String, nullable=False, unique=True)

    # relationships
    sprite: Sprite = relationship("Sprite", lazy='joined', innerjoin=True, viewonly=True)

    @property
    def filepath(self) -> str:
        return IMAGE_PATH.joinpath(self._filepath).as_posix()

    @filepath.setter
    def filepath(self, value: str):
        self._filepath = value

    @property
    def data_color(self):
        return read_data_color(self.filepath)

    @property
    def data_gray(self):
        return read_data_gray(self.filepath)

    def __repr__(self):
        return f"{SpriteFrame.__name__}({self.id=},{self._filepath=},{self.sprite_id=},{self.meta_extra=})"


class SpriteTypeLookup(Base):
    __tablename__ = 'sprite_type'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(db.Enum(SpriteType), unique=True, nullable=False)
    description = Column(String, nullable=True)

    def __repr__(self):
        return f"{self.__class__}(enum={self.name})"


class Sprite(Base):
    """A collection of sprite frames for a particular game graphic asset
    Assumptions
    1. No two sprites will share the same long_name
    2. The frames of each sprite share the same collision area
    """
    __tablename__ = "sprite"
    id = Column(Integer, primary_key=True, nullable=False)
    short_name = Column(String, nullable=False)
    long_name = Column(String, nullable=False, unique=True)
    # todo: add relationship for RealmSprite table

    type_id = Column(Integer, ForeignKey('sprite_type.id'))
    type = relationship('SpriteTypeLookup', backref='sprites', uselist=False)
    frames: list[SpriteFrame] = relationship("SpriteFrame", lazy='joined', cascade='all, delete-orphan')

    width_px = Column(Integer, nullable=True)
    height_px = Column(Integer, nullable=True)
    match_offset_x = Column(Integer, nullable=True)
    match_offset_y = Column(Integer, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': SpriteType.DECORATION.value,
        'polymorphic_on': type_id,
    }

    def __repr__(self):
        return f"{self.__tablename__}(id={self.id},short_name={self.short_name},long_name={self.long_name}, type={self.type},frames={self.frames})"

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
    story = "story"
    renegade = "renegade"
    rebel = "rebel"
    citizen = "citizen"
    resource_node = "resource node"
    # Defeat enemies that invade the realm by intereating with a cursed/haunted item
    invasion = "invasion"
    # stationary creatures must be found
    creature = "creature"

    # one of the chest in the realm is cursed
    cursed_chest = "cursed chest"


class Realm(enum.Enum):
    ARACHNID_NEST = ('Arachnid Nest', 'Cave', 'Regalis')
    AZURE_DREAM = ('Azure Dream', 'Life', "Surathli")
    BASTION_OF_THE_VOID = ('Bastion of the Void', 'Void', 'Tenebris')
    CAUSTIC_REACTOR = ('Caustic Reactor', 'Reactor', 'Venedon')
    CUTTHROAT_JUNGLE = ('Cutthroat Jungle', "Jungle", "Torun")
    BLOOD_GROVE = ('Blood Grove', "Autumn", "Apocranox")
    DEAD_SHIPS = ('Where the Dead Ships Dwell', "Underwater", "Friden")
    ETERNITY_END = ("Eternity's End", "Space", "Vertraag")
    FARAWAY_ENCLAVE = ('Faraway Enclave', "Island", "Lister")
    FROSTBITE_CAVERNS = ('Frostbite Caverns', "Snow", "Azural")
    GREAT_PANDEMONIUM = ('Great Pandemonium', "Chaos", "Vulcanar")
    KINGDOM_OF_HERETICS = ('Kingdom of Heretics', "Haunted", "Gonfurian")
    PATH_OF_THE_DAMNED = ('Path of the Damned', "Death", "Erebyss")
    REFUGE_OF_THE_MAGI = ('Refuge of the Magi', "Sorcery", "Zonte")
    SANCTUM_UMBRA = ('Sanctum Umbra', "Purgatory", "Perdition")
    TEMPLE_OF_LIES = ('Temple of Lies', "Gem", "Aurum")
    THE_BARRENS = ('The Barrens', "Desert", "Yseros")
    THE_SWAMPLANDS = ('The Swamplands', "Nature", "Meraxis")
    TITAN_WOUND = ("Titan's Wound", "BloodBone", "Mortem")
    TORTURE_CHAMBER = ('Torture Chamber', "Dungeon", "Tartarith")
    UNSULLIED_MEADOWS = ('Unsullied Meadows', "Grassland", "Aeolian")

    # new realms
    THE_FAE_LANDS = ('Fae Lands', 'Fairy', 'Shallan')
    AMALGAM_GARDENS = ('Amalgum Gardens', 'Amalgam', 'TMere Mrgo')
    ASTRAL_GALLERY = ('Astral Gallery', "Astral", "Muse")
    DAMAREL = ('Damarel', 'Damarel', "Alexandria")
    FORBIDDEN_DEPTHS = ('Forbidden Depths', "ForbiddenDepths", "Anneltha")
    FORGOTTEN_LAB = ('Forgotten Lab', "ForgottenLab", "Robo")
    GAMBLERS_HIVE = ("Gambler's Hive", 'Beehive', "Reclusa")
    LAND_OF_BALANCE = ('Land of Breath & Balance', "LandOfBalance", "Ariamaki")
    OVERGROWN_TEMPLE = ('Overgrown Temple', "OvergrownTemple", "Genaros")

    _ignore_ = ['god_to_realm_mapping', 'internal_realm_name_to_god_mapping', 'from_ingame_realm_name']
    god_to_realm_mapping: dict[str, Realm] = {}
    internal_realm_name_to_god_mapping: dict[str, Realm] = {}
    from_ingame_realm_name: dict[str, Realm] = {}

    def __init__(self, realm_name: str, internal_realm_name: str, god_name: str):
        self.realm_name = realm_name
        self.internal_realm_name = internal_realm_name
        self.god_name = god_name

    @classmethod
    def generic_realm_name_to_ingame_realm(cls, generic_realm_name: str) -> Realm:
        god_name = cls.internal_realm_name_to_god_mapping[generic_realm_name]
        return cls.god_to_realm_mapping[god_name]


Realm.god_to_realm_mapping = {realm.god_name: realm for realm in Realm}

Realm.internal_realm_name_to_god_mapping = {realm.internal_realm_name: realm for realm in Realm}
Realm.from_ingame_realm_name = {realm.realm_name: realm for realm in Realm}

UNSUPPORTED_REALMS = {

}


class RealmLookup(Base):
    __tablename__ = 'realm'
    id = Column(Integer, primary_key=True, nullable=False)
    enum = Column(db.Enum(Realm, name="enum_realm"), nullable=False, unique=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)

    god_altar_sprite = relationship("Sprite", secondary="altar_sprite", uselist=False)
    sprites = relationship("Sprite", secondary="realm_sprite", uselist=True)


class AltarSprite(Sprite):
    __tablename__ = 'altar_sprite'
    sprite_id = Column(Integer, ForeignKey('sprite.id'), unique=True, primary_key=True)
    realm_id = Column(Integer, ForeignKey('realm.id'), unique=True, primary_key=True)

    sprite = relationship('Sprite', uselist=False, viewonly=True)
    realm = relationship('RealmLookup', uselist=False, back_populates='god_altar_sprite')

    __mapper_args__ = {
        'polymorphic_identity': SpriteType.ALTAR.value
    }


class ChestType(enum.Enum):
    """Type of chest a sprite is"""
    # Normal chest placed on realm creation
    NORMAL = 1
    # Spawned from enemy defeat
    SPAWNED = 2
    # Large chest in realm
    LARGE = 3
    # A haunted/cursed chest that is part of a specific quest
    HAUNTED = 4


class ChestTypeLookup(Base):
    __tablename__ = "chest_type"
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String, unique=True, nullable=False)


class ChestSprite(Sprite):
    __tablename__ = 'chest_sprite'
    sprite_id = Column(Integer, ForeignKey('sprite.id', ondelete='CASCADE'), primary_key=True, nullable=False)
    realm_id = Column(Integer, ForeignKey('realm.id'))
    opened = Column(Boolean, nullable=False)
    chest_type_id = Column(Integer, ForeignKey('chest_type.id'), nullable=False)

    realm = relationship('RealmLookup', uselist=False)
    chest_type = relationship('ChestTypeLookup', uselist=False)

    __mapper_args__ = {
        'polymorphic_identity': SpriteType.CHEST.value
    }


class TeleportationShrine(Sprite):
    __tablename__ = None
    __mapper_args__ = {
        'polymorphic_identity': SpriteType.TELEPORTATION_SHRINE.value
    }


class TreasureMap(Sprite):
    __tablename__ = None
    __mapper_args__ = {
        'polymorphic_identity': SpriteType.TREASURE_MAP.value
    }


class LargeChest(Sprite):
    __tablename__ = None
    __mapper_args__ = {
        'polymorphic_identity': SpriteType.LARGE_CHEST.value
    }


class DemonicStatue(Sprite):
    __tablename__ = None
    __mapper_args__ = {
        'polymorphic_identity': SpriteType.DEMONIC_STATUE.value
    }


class FavorCandle(Sprite):
    __tablename__ = None
    __mapper_args__ = {
        'polymorphic_identity': SpriteType.BIG_CANDLE.value
    }


class MaterialCommon(Sprite):
    __tablename__ = None
    __mapper_args__ = {
        'polymorphic_identity': SpriteType.MATERIALS_COMMON.value
    }


class MaterialRare(Sprite):
    __tablename__ = None
    __mapper_args__ = {
        'polymorphic_identity': SpriteType.MATERIALS_RARE.value
    }


class MaterialLegendary(Sprite):
    __tablename__ = None
    __mapper_args__ = {
        'polymorphic_identity': SpriteType.MATERIALS_LEGENDARY.value
    }


class SpellMaterialBag(Sprite):
    __tablename__ = None
    __mapper_args__ = {
        'polymorphic_identity': SpriteType.SPELL_MATERIAL_BAG.value
    }

class RealmPortal(Sprite):
    __tablename__ = None
    __mapper_args__ = {
        'polymorphic_identity': SpriteType.REALM_PORTAL.value
    }



class Breakable(Sprite):
    __tablename__ = None
    __mapper_args__ = {
        'polymorphic_identity': SpriteType.BREAKABLE.value
    }


class LargeChestKey(Sprite):
    __tablename__ = None
    __mapper_args__ = {
        'polymorphic_identity': SpriteType.LARGE_CHEST_KEY.value
    }


class OverlaySprite(Sprite):
    __tablename__ = 'overlay_sprite'
    sprite_id = Column(Integer, ForeignKey('sprite.id'), unique=True, primary_key=True)
    realm_id = Column(Integer, ForeignKey('realm.id'), unique=True, primary_key=True)

    realm = relationship('RealmLookup', uselist=False)

    __mapper_args__ = {
        'polymorphic_identity': SpriteType.OVERLAY.value
    }


class RealmSprite(Base):
    __tablename__ = 'realm_sprite'
    realm_id = Column(Integer, ForeignKey('realm.id'), nullable=False, primary_key=True)
    sprite_id = Column(Integer, ForeignKey('sprite.id'), nullable=False, primary_key=True, unique=True)


class FloorSprite(Sprite):
    __tablename__ = "floor_sprite"
    sprite_id = Column(Integer, ForeignKey('sprite.id'), nullable=False, primary_key=True, unique=True)
    realm_id = Column(Integer, ForeignKey('realm.id'), nullable=True, index=True)

    sprite = relationship('Sprite', uselist=False, viewonly=True, lazy='joined')
    realm = relationship('RealmLookup', uselist=False, viewonly=True)

    __mapper_args__ = {
        'polymorphic_identity': SpriteType.FLOOR.value,
    }


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


class ProjectItemSprite(Sprite):
    __tablename__ = "project_item_sprite"
    sprite_id = Column(Integer, ForeignKey('sprite.id'), nullable=False, primary_key=True, unique=True)

    sprite = relationship('Sprite', uselist=False, viewonly=True, lazy='joined')

    __mapper_args__ = {
        'polymorphic_identity': SpriteType.PROJ_ITEM.value
    }


class ResourceNodeSprite(Sprite):
    __tablename__ = "resource_node_sprite"
    sprite_id = Column(Integer, ForeignKey('sprite.id'), nullable=False, primary_key=True)
    realm_id = Column(Integer, ForeignKey('realm.id'), nullable=False, primary_key=True)

    sprite = relationship('Sprite', uselist=False, viewonly=True, lazy='joined')
    realm = relationship('RealmLookup', uselist=False, viewonly=True)

    __mapper_args__ = {
        'polymorphic_identity': SpriteType.RESOURCE_NODE.value
    }


class Quest(Base):
    """Info about how to complete the quest

    model assumptions
    * Each quest has a unique title
    * A quest will either have the requirement be unique to the realm, OR it will be available in all realms
    """
    __tablename__ = 'quest'
    id = Column(Integer, primary_key=True, nullable=False)

    # internal quest id used in-game
    qid = Column(Integer, unique=True, nullable=True)

    title = Column(String, nullable=False, unique=True, index=True)

    _computed_title_first_line_sql = """CASE
    WHEN instr(title, "\r\n") > 0
    THEN substr(title, 0, instr(title, "\r\n"))
    ELSE title END"""
    _computed_title_first_line_obj = db.Computed(_computed_title_first_line_sql)

    title_first_line = Column(String, _computed_title_first_line_obj, nullable=False, index=True)
    quest_type = Column(db.Enum(QuestType, name="enum_quest_type"), nullable=False)

    # What realm the quest is tied to. Null if non-specific
    specific_realm_id = Column('specific_realm', Integer, ForeignKey('realm.id'), nullable=True)

    supported = Column(Boolean, nullable=False, default=True)
    description = Column(String, nullable=True)

    sprites = relationship('Sprite', secondary="quest_sprite", uselist=True, lazy='joined',
                           doc="returns 0 or more sprites associated with a realm quest")
    specific_realm = relationship('RealmLookup', uselist=False)

    def __repr__(self):
        return f"Quest({self.id=}, {self.title=}, {self.quest_type=}, {self.specific_realm_id=}, {self.sprites=}"


class QuestSprite(Base):
    __tablename__ = 'quest_sprite'
    quest_id = Column(ForeignKey('quest.id'), primary_key=True, nullable=False)
    sprite_id = Column(ForeignKey('sprite.id'), primary_key=True, nullable=False)


class NPCSprite(Sprite):
    __tablename__ = "npc_sprite"
    sprite_id = Column(Integer, ForeignKey('sprite.id'), nullable=False, primary_key=True, unique=True)
    realm_id = Column(Integer, ForeignKey('realm.id'), nullable=True, index=True)

    sprite = relationship('Sprite', uselist=False, viewonly=True, lazy='joined')
    realm = relationship('RealmLookup', uselist=False, viewonly=True)

    __mapper_args__ = {
        'polymorphic_identity': SpriteType.NPC.value
    }


class MasterNPCSprite(Sprite):
    __tablename__ = "master_npc_sprite"
    sprite_id = Column(Integer, ForeignKey('sprite.id'), nullable=False, primary_key=True, unique=True)

    sprite = relationship('Sprite', uselist=False, viewonly=True, lazy='joined')

    __mapper_args__ = {
        'polymorphic_identity': SpriteType.MASTER_NPC.value
    }


class CastleSprite(Sprite):
    __tablename__ = "castle_sprite"
    sprite_id = Column(Integer, ForeignKey('sprite.id'), nullable=False, primary_key=True, unique=True)

    sprite = relationship('Sprite', uselist=False, viewonly=True, lazy='joined')

    __mapper_args__ = {
        'polymorphic_identity': SpriteType.CASTLE_DECORATION.value
    }


class WallSprite(Sprite):
    __tablename__ = "wall_sprite"
    sprite_id = Column(Integer, ForeignKey('sprite.id'), nullable=False, primary_key=True)
    realm_id = Column(Integer, ForeignKey('realm.id'), nullable=False, primary_key=True)

    sprite = relationship('Sprite', uselist=False, viewonly=True, lazy='joined')
    realm = relationship('RealmLookup', uselist=False, viewonly=True)

    __mapper_args__ = {
        'polymorphic_identity': SpriteType.WALL.value
    }


class EnemySprite(Sprite):
    __tablename__ = "enemy_sprite"
    sprite_id = Column(Integer, ForeignKey('sprite.id'), nullable=False, primary_key=True, unique=True)
    realm_id = Column(Integer, ForeignKey('realm.id'), nullable=True, index=True)

    sprite = relationship('Sprite', uselist=False, viewonly=True, lazy='joined')
    realm = relationship('RealmLookup', uselist=False, viewonly=True)

    __mapper_args__ = {
        'polymorphic_identity': SpriteType.ENEMY.value
    }


class CreatureSprite(Sprite):
    __tablename__ = "creature_sprite"
    sprite_id = Column(Integer, ForeignKey('sprite.id'), nullable=False, primary_key=True, unique=True)
    realm_id = Column(Integer, ForeignKey('realm.id'), nullable=True, index=True)

    sprite = relationship('Sprite', uselist=False, viewonly=True, lazy='joined')
    realm = relationship('RealmLookup', uselist=False, viewonly=True)

    __mapper_args__ = {
        'polymorphic_identity': SpriteType.CREATURE.value
    }


class HashFrameWithFloor(Base):
    """Perceptual hashes using phash algorithm for all sprite frame + floortile combinations"""
    __tablename__ = "sprite_frame_hash"

    sprite_frame_id = Column(Integer, ForeignKey('sprite_frame.id'), nullable=False)
    floor_sprite_frame_id = Column(Integer, ForeignKey('sprite_frame.id'), nullable=False, primary_key=True)
    phash = Column(Integer, nullable=False, primary_key=True)

    sprite = relationship('Sprite',
                          primaryjoin=sprite_frame_id == SpriteFrame.id,
                          secondary=SpriteFrame.__table__,
                          secondaryjoin=SpriteFrame.sprite_id == Sprite.id, uselist=False, viewonly=True,
                          innerjoin=True)


if __name__ == "__main__":
    engine = create_engine(DATABASE_CONFIG.uri, echo=True)
    Base.metadata.create_all(engine)
