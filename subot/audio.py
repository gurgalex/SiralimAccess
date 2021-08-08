from __future__ import annotations
import enum
from dataclasses import dataclass
from enum import auto
from pathlib import Path
from typing import Optional

import pygame
import win32com.client

from subot.pathfinder.map import TileType
from subot.utils import Point


@dataclass
class AudioLocation:
    distance: Point


Left = float
Right = float


class SoundType(enum.Enum):
    ALTAR = auto()
    CHEST = auto()
    MASTER_NPC = auto()
    NPC_NORMAL = auto()
    PROJECT_ITEM = auto()
    QUEST_ITEM = auto()
    REACHABLE_BLACK = auto()
    TELEPORTATION_SHRINE = auto()

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
        else:
            raise KeyError(f)


@dataclass
class SoundIndicator:
    low: pygame.mixer.Sound
    normal: pygame.mixer.Sound
    high: pygame.mixer.Sound


@dataclass
class SoundMapping:
    channel: pygame.mixer.Channel
    sounds: SoundIndicator


AUDIO_DIR = (Path.cwd() / __file__).parent.parent.joinpath("resources").joinpath('audio')

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
            SoundType.REACHABLE_BLACK: SoundMapping(
                channel=pygame.mixer.Channel(8),
                sounds=SoundIndicator(
                    low=pygame.mixer.Sound(AUDIO_DIR.joinpath("tone-low.wav").as_posix()),
                    normal=pygame.mixer.Sound(AUDIO_DIR.joinpath("tone-normal.wav").as_posix()),
                    high=pygame.mixer.Sound(AUDIO_DIR.joinpath("tone-high.wav").as_posix()),
                )
            ),

        }

        # Windows TTS speaker
        self.Speaker = win32com.client.Dispatch("SAPI.SpVoice")
        # don't block the program when speaking. Cancel any pending speaking directions
        self.SVSFlag = 3  # SVSFlagsAsync = 1 + SVSFPurgeBeforeSpeak = 2
        self.Speaker.Voice = self.Speaker.getVoices('Name=Microsoft Zira Desktop').Item(0)

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

        if channel.get_sound() != sound:
            channel.play(sound, -1)
            channel.set_volume(*volume)

        channel.set_volume(*volume)

    def stop(self, sound_type: SoundType):
        self.sound_mappings[sound_type].channel.stop()

    def speak_blocking(self, text):
        self.Speaker.Speak(text)

    def speak_nonblocking(self, text):
        self.Speaker.Speak(text, self.SVSFlag)
