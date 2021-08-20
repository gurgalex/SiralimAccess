from __future__ import annotations
import enum
import socketserver
from dataclasses import dataclass
from enum import auto
from pathlib import Path
from typing import Optional, Union

import pygame
import win32com.client
from time import sleep

from subot.pathfinder.map import TileType
from subot.utils import Point


@dataclass
class AudioLocation:
    distance: Point


Left = float
Right = float


class SoundType(enum.Enum):
    ALTAR = (auto(), "altar")
    CHEST = (auto(), "chest")
    MASTER_NPC = (auto(), "master")
    NPC_NORMAL = (auto(), "NPC")
    PROJECT_ITEM = (auto(), "project item")
    QUEST_ITEM = (auto(), "quest item")
    REACHABLE_BLACK = (auto(), "untraveled tile")
    REACHABLE_DIRECTION = (auto(), "direction can travel")
    TELEPORTATION_SHRINE = (auto(), "teleportation shrine")

    def __init__(self, number, description):
        self.number = number
        self.description = description

    @classmethod
    def from_tile_type(cls, f: TileType) -> SoundType:
        """raises: KeyError if no sound exists for varient of FoundType"""
        if f is TileType.ALTAR:
            return SoundType.ALTAR
        elif f is TileType.CHEST:
            return SoundType.CHEST
        elif f is TileType.QUEST:
            return SoundType.QUEST_ITEM
        elif f is TileType.MASTER_NPC:
            return SoundType.MASTER_NPC
        elif f is TileType.NPC:
            return SoundType.NPC_NORMAL
        elif f is TileType.PROJECT_ITEM:
            return SoundType.PROJECT_ITEM
        elif f is TileType.TELEPORTATION_SHRINE:
            return SoundType.TELEPORTATION_SHRINE
        # elif f is TileType.REACHABLE_DIRECTION:
        #     return SoundType.REACHABLE_DIRECTION
        # elif f is TileType.REACHABLE_BLACK:
        #     return SoundType.REACHABLE_BLACK
        else:
            raise KeyError(f)


@dataclass
class SoundIndicator:
    low: pygame.mixer.Sound
    normal: pygame.mixer.Sound
    high: pygame.mixer.Sound


@dataclass
class SoundMapping:
    channel: Union[dict[str, pygame.mixer.Channel], pygame.mixer.Channel]
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
        return Left(1 / (abs(distance.y) + 1)), \
               Right(1 / (abs(distance.y) + 1))


class AudioSystem:
    def __init__(self):
        pygame.mixer.set_num_channels(16)
        self.sound_mappings: dict[SoundType, SoundMapping] = {
            SoundType.ALTAR: SoundMapping(
                channel=pygame.mixer.Channel(2),
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("altar-angel-low.ogg").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("altar-angel-normal.ogg").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("altar-angel-high.ogg").as_posix()),
                )
            ),

            SoundType.MASTER_NPC: SoundMapping(
                channel=pygame.mixer.Channel(5),
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("horse_sound_cc0-low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("horse_sound_cc0.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("horse_sound_cc0-high.wav").as_posix()),
                )
            ),

            SoundType.NPC_NORMAL: SoundMapping(
                channel=pygame.mixer.Channel(4),
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("npc-low.ogg").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("npc-normal.ogg").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("npc-high.ogg").as_posix()),
                )
            ),

            SoundType.PROJECT_ITEM: SoundMapping(
                channel=pygame.mixer.Channel(3),
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("project-item-low.ogg").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("project-item-normal.ogg").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("project-item-high.ogg").as_posix()),
                )
            ),

            SoundType.QUEST_ITEM: SoundMapping(
                channel=pygame.mixer.Channel(0),
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("tone-low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("tone-normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("tone-high.wav").as_posix()),
                )
            ),

            SoundType.TELEPORTATION_SHRINE: SoundMapping(
                channel=pygame.mixer.Channel(6),
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath('teleportation-shrine/low.ogg').as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath('teleportation-shrine/normal.ogg').as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath('teleportation-shrine/high.ogg').as_posix()),
                )
            ),
            SoundType.CHEST: SoundMapping(
                channel=pygame.mixer.Channel(7),
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("snd_ChestOpening/low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("snd_ChestOpening/normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("snd_ChestOpening/high.wav").as_posix()),
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
        self.Speaker.Voice = self.Speaker.getVoices('Name=Microsoft Zira Desktop').Item(0)
        self.Speaker.Rate = 5

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

        if channel.get_sound() != sound:
            channel.play(sound, -1)
            channel.set_volume(*volume)

        channel.set_volume(*volume)

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
        self.Speaker.Speak(text)

    def speak_nonblocking(self, text):
        self.Speaker.Speak(text, self.SVSFlag)

    def get_available_sounds(self) -> dict[SoundType, SoundMapping]:
        return self.sound_mappings

    def play_sound_demo(self, sound_type: SoundType, play_for_seconds: float):
        # self.speak_blocking(sound_type.description)

        sounds = self.sound_mappings[sound_type]
        for sound_name, sound_type in sounds.sounds_as_dict().items():

            self.speak_blocking(sound_name)
            sound_type.play(-1)
            sleep(play_for_seconds)
            sound_type.stop()
