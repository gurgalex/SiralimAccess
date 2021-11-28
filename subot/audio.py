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
    EMBLEM = (auto(), 'emblem')
    EXOTIC_PORTAL = (auto(), 'exotic portal')
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
    TileType.EMBLEM: SoundType.EMBLEM,
    TileType.EXOTIC_PORTAL: SoundType.EXOTIC_PORTAL,
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
    TileType.WARDROBE: SoundType.WARDROBE
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

            # SoundType.REACHABLE_BLACK: SoundMapping(
            #     channel=pygame.mixer.Channel(8),
            #     sounds=SoundIndicator(
            #         low=pygame.mixer.Sound(AUDIO_DIR.joinpath("tone-low.wav").as_posix()),
            #         normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("tone-normal.wav").as_posix()),
            #         high=pygame.mixer.Sound(AUDIO_DIR.joinpath("tone-high.wav").as_posix()),
            #     )
            # ),
            #
            # SoundType.REACHABLE_DIRECTION: SoundMapping(
            #     channel={
            #         "up": pygame.mixer.Channel(9),
            #         "down": pygame.mixer.Channel(10),
            #         "left": pygame.mixer.Channel(11),
            #         "right": pygame.mixer.Channel(12),
            #     },
            #     sounds=SoundIndicator(
            #         # low=pygame.mixer.Sound(AUDIO_DIR.joinpath("wall-thud-low.wav").as_posix()),
            #         # normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("wall-thud-normal.wav").as_posix()),
            #         # high=pygame.mixer.Sound(AUDIO_DIR.joinpath("wall-thud-high.wav").as_posix()),
            #         low=pygame.mixer.Sound(AUDIO_DIR.joinpath("laser3-low.wav").as_posix()),
            #         normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("tone-normal.wav").as_posix()),
            #         high=pygame.mixer.Sound(AUDIO_DIR.joinpath("laser3.wav").as_posix()),
            #     )
            # ),

        }

        # Windows TTS speaker
        self.Speaker = win32com.client.Dispatch("SAPI.SpVoice")
        # don't block the program when speaking. Cancel any pending speaking directions
        self.SVSFlag = 3  # SVSFlagsAsync = 1 + SVSFPurgeBeforeSpeak = 2

    def play_sound(self, audio_tile: AudioLocation, sound_type: SoundType):
        distance_y = audio_tile.distance.y

        sound_mapping = self.sound_mappings[sound_type]
        channel = sound_mapping.channel

        # if sound_type is SoundType.REACHABLE_DIRECTION:
        #     position = audio_tile.distance
        #     if position == Point(0,1):
        #         channel = channel["down"]
        #     elif position == Point(0,-1):
        #         channel = channel["up"]
        #     elif position == Point(1, 0):
        #         channel = channel["right"]
        #     elif position == Point(-1, 0):
        #         channel = channel["left"]

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
        channel = self.sound_mappings[sound_type].channel
        # if sound_type is SoundType.REACHABLE_DIRECTION:
        #     position = point
        #     if not point:
        #         for chan in channel.values():
        #             chan.stop()
        #         return
        #
        #     if position == Point(0,1):
        #         channel = channel["down"]
        #     elif position == Point(0,-1):
        #         channel = channel["up"]
        #     elif position == Point(1, 0):
        #         channel = channel["right"]
        #     elif position == Point(-1, 0):
        #         channel = channel["left"]
        channel.stop()

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
