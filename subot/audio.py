from dataclasses import dataclass
from typing import Optional

import pygame
import win32com.client

from subot.utils import Point


@dataclass
class AudioLocation:
    distance: Point


Left = float
Right = float


def volume_from_distance(distance: Point) -> tuple[Left, Right]:
    if distance.x > 0:
        return Left(0),\
               Right(1 / (distance.x + 1 + abs(distance.y)))
    elif distance.x < 0:
        return Left(1 / (abs(abs(distance.x) + abs(distance.y)) + 1)),\
               Right(0)
    else:
        return Left(1 / (abs(distance.y) + 1)),\
               Right(1 / (abs(distance.y) + 1))


class AudioSystem:
    def __init__(self):
        self.altar_low_sound = pygame.mixer.Sound("../audio/altar-low.wav")
        self.altar_normal_sound = pygame.mixer.Sound("../audio/altar_normal-amplifiedl.wav")
        self.altar_high_sound = pygame.mixer.Sound("../audio/altar-high.wav")

        self.master_npc_low_sound = pygame.mixer.Sound("../audio/horse_sound_cc0-low.wav")
        self.master_npc_normal_sound = pygame.mixer.Sound("../audio/horse_sound_cc0.wav")
        self.master_npc_high_sound = pygame.mixer.Sound("../audio/horse_sound_cc0-high.wav")

        self.quest_item_normal_sound = pygame.mixer.Sound("../audio/tone-normal.wav")
        self.quest_item_high_sound = pygame.mixer.Sound("../audio/tone-high.wav")
        self.quest_item_low_sound = pygame.mixer.Sound("../audio/tone-low.wav")

        self.quest_channel = pygame.mixer.Channel(0)

        # audio channel for master NPC sound
        self.master_npc_channel = pygame.mixer.Channel(1)

        # audio channel for realm realm altar sound
        self.altar_channel = pygame.mixer.Channel(2)


        # Windows TTS speaker
        self.Speaker = win32com.client.Dispatch("SAPI.SpVoice")
        # don't block the program when speaking. Cancel any pending speaking directions
        self.SVSFlag = 3  # SVSFlagsAsync = 1 + SVSFPurgeBeforeSpeak = 2
        self.Speaker.Voice = self.Speaker.getVoices('Name=Microsoft Zira Desktop').Item(0)

    def play_altar(self, audio_location: AudioLocation):
        audio_tile = audio_location
        distance_y = audio_tile.distance.y

        if distance_y > 0:
            sound = self.altar_low_sound
        elif distance_y < 0:
            sound = self.altar_high_sound
        else:
            sound = self.altar_normal_sound

        volume = volume_from_distance(audio_tile.distance)
        if self.altar_channel.get_sound() != sound:
            self.altar_channel.play(sound, -1)
            self.altar_channel.set_volume(*volume)

        self.altar_channel.set_volume(*volume)

    def stop_altar(self):
        self.altar_channel.stop()



    def stop_master(self):
        """stop playing item nearness sound if no objects are detected in range"""
        self.master_npc_channel.stop()

    def play_master(self, master_location: AudioLocation):

        audio_tile = master_location
        distance_y = audio_tile.distance.y

        if distance_y > 0:
            sound = self.master_npc_low_sound
        elif distance_y < 0:
            sound = self.master_npc_high_sound
        else:
            sound = self.master_npc_normal_sound

        volume = volume_from_distance(audio_tile.distance)
        if self.master_npc_channel.get_sound() != sound:
            self.master_npc_channel.play(sound, -1)
            self.master_npc_channel.set_volume(*volume)

        self.master_npc_channel.set_volume(*volume)

    def play_quest_items(self, audio_locations: list[AudioLocation]):
        no_locations = len(audio_locations) == 0
        # stop playing item nearness sound if no objects are detected in range
        if no_locations:
            self.quest_channel.stop()
            return

        for audio_tile in audio_locations[:1]:
            distance_y = audio_tile.distance.y

            if distance_y > 0:
                sound = self.quest_item_low_sound
            elif distance_y < 0:
                sound = self.quest_item_high_sound
            else:
                sound = self.quest_item_normal_sound

            volume = volume_from_distance(audio_tile.distance)

            if self.quest_channel.get_sound() != sound:
                self.quest_channel.play(sound, -1)
                self.quest_channel.set_volume(*volume)

            self.quest_channel.set_volume(*volume)
