from __future__ import annotations
import enum
from dataclasses import dataclass
from enum import auto
from pathlib import Path
from typing import Optional, Union

import pygame
import win32com.client
from time import sleep

from subot.pathfinder.map import TileType
from subot.settings import Config
from subot.utils import Point

from cytolk import tolk
tolk.try_sapi(False)

@dataclass
class AudioLocation:
    distance: Point


Left = float
Right = float


class SoundType(enum.Enum):
    _ignore_ = ["mapping"]
    ALTAR = (auto(), "altar")
    BLACKSMITH = (auto(), "blacksmith")
    CHEST = (auto(), "chest")
    DIVINATION_CANDLE = (auto(), 'divination candle')
    EMBLEM = (auto(), 'emblem')
    ENCHANTER = (auto(), 'enchanter')
    EXOTIC_PORTAL = (auto(), 'exotic portal')
    REALM_PORTAL = (auto(), 'realm portal')
    MASTER_NPC = (auto(), "master")
    NPC_NORMAL = (auto(), "NPC")
    PANDEMONIUM_STATUE = (auto(), 'pandemonium statue')
    PROJECT_ITEM = (auto(), "project item")
    QUEST_ITEM = (auto(), "quest item")
    REACHABLE_BLACK = (auto(), "untraveled tile")
    REACHABLE_DIRECTION = (auto(), "direction can travel")
    RIDDLE_DWARF = (auto(), 'riddle_dwarf')
    NETHER_PORTAL = (auto(), "nether portal")
    SUMMONING = (auto(), 'summoning brazier')
    TELEPORTATION_SHRINE = (auto(), "teleportation shrine")
    TREASURE_MAP_ITEM = (auto(), 'treasure map item')
    WARDROBE = (auto(), 'wardrobe')
    EVERETT = (auto(), 'everett')
    MENAGERIE_NPC = (auto(), 'menagerie NPC')
    LARGE_CHEST = (auto(), 'large chest')
    FAVOR_CANDLE = (auto(), 'favor candle')
    LARGE_CHEST_KEY = (auto(), "large key")
    MATERIALS_COMMON = (auto(), "common artifact materials")
    MATERIALS_RARE = (auto(), "trick artifact materials")
    MATERIALS_LEGENDARY = (auto(), "trait artifact materials")
    GEMBAG = (auto(), "spell crafting materials")

    mapping: dict[TileType, SoundType] = {}

    def __init__(self, number, description):
        self.number = number
        self.description = description

    @classmethod
    def from_tile_type(cls, f: TileType) -> SoundType:
        """raises: KeyError if no sound exists for varient of FoundType"""
        return cls.mapping[f]


SoundType.mapping = {
    TileType.ALTAR: SoundType.ALTAR,
    TileType.BLACKSMITH: SoundType.BLACKSMITH,
    TileType.CHEST: SoundType.CHEST,
    TileType.DIVINATION_CANDLE: SoundType.DIVINATION_CANDLE,
    TileType.EMBLEM: SoundType.EMBLEM,
    TileType.ENCHANTER: SoundType.ENCHANTER,
    TileType.EXOTIC_PORTAL: SoundType.EXOTIC_PORTAL,
    TileType.REALM_PORTAL: SoundType.REALM_PORTAL,
    TileType.QUEST: SoundType.QUEST_ITEM,
    TileType.MASTER_NPC: SoundType.MASTER_NPC,
    TileType.NPC: SoundType.NPC_NORMAL,
    TileType.PROJECT_ITEM: SoundType.PROJECT_ITEM,
    TileType.TELEPORTATION_SHRINE: SoundType.TELEPORTATION_SHRINE,
    TileType.NETHER_PORTAL: SoundType.NETHER_PORTAL,
    TileType.SUMMONING: SoundType.SUMMONING,
    TileType.RIDDLE_DWARF: SoundType.RIDDLE_DWARF,
    TileType.PANDEMONIUM_STATUE: SoundType.PANDEMONIUM_STATUE,
    TileType.TREASURE_MAP_ITEM: SoundType.TREASURE_MAP_ITEM,
    TileType.WARDROBE: SoundType.WARDROBE,
    TileType.EVERETT: SoundType.EVERETT,
    TileType.MENAGERIE_NPC: SoundType.MENAGERIE_NPC,
    TileType.LARGE_CHEST: SoundType.LARGE_CHEST,
    TileType.LARGE_CHEST_KEY: SoundType.LARGE_CHEST_KEY,
    TileType.FAVOR_CANDLE: SoundType.FAVOR_CANDLE,
    TileType.ARTIFACT_MATERIAL_BAG: SoundType.MATERIALS_COMMON,
    TileType.TRICK_MATERIAL_BOX: SoundType.MATERIALS_RARE,
    TileType.TRAIT_MATERIAL_BOX: SoundType.MATERIALS_LEGENDARY,
    TileType.SPELL_MATERIAL_BAG: SoundType.GEMBAG,
}


@dataclass
class SoundIndicator:
    low: pygame.mixer.Sound
    normal: pygame.mixer.Sound
    high: pygame.mixer.Sound


@dataclass
class SoundMapping:
    channel: Union[dict[str, pygame.mixer.Channel], pygame.mixer.Channel]
    volume_adj: int
    sounds: SoundIndicator

    def sounds_as_dict(self) -> dict[str, pygame.mixer.Sound]:
        return {
            "down": self.sounds.low,
            "level": self.sounds.normal,
            "up": self.sounds.high,
        }


AUDIO_DIR = (Path.cwd() / __file__).parent.parent.joinpath("resources").joinpath('audio')


def volume_from_distance(distance: Point) -> tuple[Left, Right]:
    if distance.x > 0:
        return Left(0), \
               Right(1 / (distance.x + 1 + abs(distance.y)))
    elif distance.x < 0:
        return Left(1 / (abs(abs(distance.x) + abs(distance.y)) + 1)), \
               Right(0)
    else:
        return Left((1 / (abs(distance.y) + 1))), \
               Right((1 / (abs(distance.y) + 1)))


class AudioSystem:
    def __init__(self, config: Config):
        self.config = config
        self.silenced: bool = False
        pygame.mixer.set_num_channels(32)
        self.sound_mappings: dict[SoundType, SoundMapping] = {
            SoundType.ALTAR: SoundMapping(
                channel=pygame.mixer.Channel(2),
                volume_adj=self.config.altar,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("altar-angel-low.ogg").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("altar-angel-normal.ogg").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("altar-angel-high.ogg").as_posix()),
                )
            ),

            SoundType.MASTER_NPC: SoundMapping(
                channel=pygame.mixer.Channel(5),
                volume_adj=self.config.npc_master,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("horse_sound_cc0-low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("horse_sound_cc0.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("horse_sound_cc0-high.wav").as_posix()),
                )
            ),

            SoundType.NPC_NORMAL: SoundMapping(
                channel=pygame.mixer.Channel(4),
                volume_adj=self.config.npc_generic,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("npc-low.ogg").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("npc-normal.ogg").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("npc-high.ogg").as_posix()),
                )
            ),

            SoundType.PROJECT_ITEM: SoundMapping(
                channel=pygame.mixer.Channel(3),
                volume_adj=self.config.project_item,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("project-item-low.ogg").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("project-item-normal.ogg").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("project-item-high.ogg").as_posix()),
                )
            ),

            SoundType.QUEST_ITEM: SoundMapping(
                channel=pygame.mixer.Channel(0),
                volume_adj=self.config.quest,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("quest-item/low-2.ogg").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("quest-item/normal.ogg").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("quest-item/high.ogg").as_posix()),
                )
            ),

            SoundType.TELEPORTATION_SHRINE: SoundMapping(
                channel=pygame.mixer.Channel(6),
                volume_adj=self.config.teleportation_shrine,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath('teleportation-shrine/low.ogg').as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath('teleportation-shrine/normal.ogg').as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath('teleportation-shrine/high.ogg').as_posix()),
                )
            ),
            SoundType.CHEST: SoundMapping(
                channel=pygame.mixer.Channel(7),
                volume_adj=self.config.chest,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("snd_ChestOpening/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("snd_ChestOpening/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("snd_ChestOpening/high.wav").as_posix()),
                )
            ),
            SoundType.NETHER_PORTAL: SoundMapping(
                channel=pygame.mixer.Channel(8),
                volume_adj=self.config.nether_portal,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("nether-portal-low.ogg").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("nether-portal-normal.ogg").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("nether-portal-high.ogg").as_posix()),
                )
            ),
            SoundType.SUMMONING: SoundMapping(
                channel=pygame.mixer.Channel(9),
                volume_adj=self.config.summoning_brazier,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("summoning-low.ogg").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("summoning-normal.ogg").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("summoning-high.ogg").as_posix()),
                )
            ),
            SoundType.RIDDLE_DWARF: SoundMapping(
                channel=pygame.mixer.Channel(10),
                volume_adj=self.config.riddle_dwarf,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("riddle-dwarf/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("riddle-dwarf/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("riddle-dwarf/high.wav").as_posix()),
                )
            ),
            SoundType.PANDEMONIUM_STATUE: SoundMapping(
                channel=pygame.mixer.Channel(11),
                volume_adj=self.config.pandemonium_statue,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("pand-statue/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("pand-statue/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("pand-statue/high.wav").as_posix()),
                )
            ),
            SoundType.TREASURE_MAP_ITEM: SoundMapping(
                channel=pygame.mixer.Channel(12),
                volume_adj=self.config.treasure_map_item,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("treasure-map-item/low.ogg").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("treasure-map-item/normal.ogg").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("treasure-map-item/high.ogg").as_posix()),
                )
            ),
            SoundType.EXOTIC_PORTAL: SoundMapping(
                channel=pygame.mixer.Channel(13),
                volume_adj=self.config.exotic_portal,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("exotic-portal/low.ogg").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("exotic-portal/normal.ogg").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("exotic-portal/high.ogg").as_posix()),
                )
            ),
            SoundType.EMBLEM: SoundMapping(
                channel=pygame.mixer.Channel(14),
                volume_adj=self.config.emblem,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("emblem/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("emblem/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("emblem/high.wav").as_posix()),
                )
            ),
            SoundType.DIVINATION_CANDLE: SoundMapping(
                channel=pygame.mixer.Channel(15),
                volume_adj=self.config.divination_candle,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("divination-candle/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("divination-candle/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("divination-candle/high.wav").as_posix()),
                )
            ),
            SoundType.WARDROBE: SoundMapping(
                channel=pygame.mixer.Channel(16),
                volume_adj=self.config.wardrobe,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("wardrobe/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("wardrobe/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("wardrobe/high.wav").as_posix()),
                )
            ),
            SoundType.BLACKSMITH: SoundMapping(
                channel=pygame.mixer.Channel(17),
                volume_adj=self.config.blacksmith,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("blacksmith/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("blacksmith/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("blacksmith/high.wav").as_posix()),
                )
            ),
            SoundType.ENCHANTER: SoundMapping(
                channel=pygame.mixer.Channel(18),
                volume_adj=self.config.enchanter,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("enchanter/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("enchanter/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("enchanter/high.wav").as_posix()),
                )
            ),
            SoundType.EVERETT: SoundMapping(
                channel=pygame.mixer.Channel(19),
                volume_adj=self.config.everett,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("everett/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("everett/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("everett/high.wav").as_posix()),
                )
            ),
            SoundType.MENAGERIE_NPC: SoundMapping(
                channel=pygame.mixer.Channel(20),
                volume_adj=self.config.menagerie,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("menagerie/low.ogg").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("menagerie/normal.ogg").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("menagerie/high.ogg").as_posix()),
                )
            ),
            SoundType.LARGE_CHEST: SoundMapping(
                channel=pygame.mixer.Channel(21),
                volume_adj=self.config.large_chest,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("large-chest/low.ogg").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("large-chest/normal.ogg").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("large-chest/high.ogg").as_posix()),
                )
            ),
            SoundType.FAVOR_CANDLE: SoundMapping(
                channel=pygame.mixer.Channel(22),
                volume_adj=self.config.favor_candle,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("favor-candle/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("favor-candle/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("favor-candle/high.wav").as_posix()),
                )
            ),
            SoundType.MATERIALS_COMMON: SoundMapping(
                channel=pygame.mixer.Channel(23),
                volume_adj=self.config.materials_common_artifact,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("materials-common/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("materials-common/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("materials-common/high.wav").as_posix()),
                )
            ),
            SoundType.MATERIALS_RARE: SoundMapping(
                channel=pygame.mixer.Channel(24),
                volume_adj=self.config.materials_trick_artifact,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("materials-rare/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("materials-rare/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("materials-rare/high.wav").as_posix()),
                )
            ),
            SoundType.MATERIALS_LEGENDARY: SoundMapping(
                channel=pygame.mixer.Channel(25),
                volume_adj=self.config.materials_trait_artifact,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("materials-legendary/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("materials-legendary/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("materials-legendary/high.wav").as_posix()),
                )
            ),
            SoundType.GEMBAG: SoundMapping(
                channel=pygame.mixer.Channel(26),
                volume_adj=self.config.gembag,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("gembag/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("gembag/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("gembag/high.wav").as_posix()),
                )
            ),
            SoundType.LARGE_CHEST_KEY: SoundMapping(
                channel=pygame.mixer.Channel(27),
                volume_adj=self.config.large_chest_key,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("large-chest-key/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("large-chest-key/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("large-chest-key/high.wav").as_posix()),
                )
            ),
            SoundType.REALM_PORTAL: SoundMapping(
                channel=pygame.mixer.Channel(28),
                volume_adj=self.config.realm_portal,
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("realm-portal/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("realm-portal/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("realm-portal/high.wav").as_posix()),
                )
            ),
        }

        # Windows TTS speaker
        self.Speaker = win32com.client.Dispatch("SAPI.SpVoice")
        # don't block the program when speaking. Cancel any pending speaking directions
        self.SVSFlag = 3  # SVSFlagsAsync = 1 + SVSFPurgeBeforeSpeak = 2

    def play_sound(self, audio_tile: AudioLocation, sound_type: SoundType):
        distance_y = audio_tile.distance.y

        sound_mapping = self.sound_mappings[sound_type]
        channel = sound_mapping.channel

        if distance_y > 0:
            sound = sound_mapping.sounds.low
        elif distance_y < 0:
            sound = sound_mapping.sounds.high
        else:
            sound = sound_mapping.sounds.normal

        volume = volume_from_distance(audio_tile.distance)

        volume_adj = self.config.master_volume / 100 * sound_mapping.volume_adj / 100
        adjusted_volume = volume[0] * volume_adj, volume[1] * volume_adj

        if channel.get_sound() != sound:
            channel.play(sound, -1)
            channel.set_volume(*adjusted_volume)

        channel.set_volume(*adjusted_volume)

    def stop(self, sound_type: SoundType, point: Optional[Point]=None):
        try:
            channel = self.sound_mappings[sound_type].channel
            channel.stop()
        except KeyError:
            return

    def speak_blocking(self, text):
        self.silenced = False
        with tolk.tolk():
            if tolk.has_speech():
                tolk.speak(text, interrupt=False)
            else:
                self.Speaker.Speak(text)

    def speak_nonblocking(self, text):
        self.silenced = False
        with tolk.tolk():
            if tolk.has_speech():
                tolk.speak(text, interrupt=True)
            else:
                self.Speaker.Speak(text, self.SVSFlag)

    def silence(self):
        if self.silenced:
            return
        with tolk.tolk():
            if tolk.has_speech():
                tolk.silence()
            else:
                self.speak_nonblocking(' ')
        self.silenced = True

    def get_available_sounds(self) -> dict[SoundType, SoundMapping]:
        return self.sound_mappings

    def play_sound_demo(self, sound_type: SoundType, play_for_seconds: float):

        sounds = self.sound_mappings[sound_type]
        for sound_name, sound_type in sounds.sounds_as_dict().items():

            self.speak_blocking(sound_name)
            sound_type.play(-1)
            sleep(play_for_seconds)
            sound_type.stop()
