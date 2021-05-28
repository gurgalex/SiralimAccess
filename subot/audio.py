from dataclasses import dataclass
import pygame
import win32com.client

from subot.utils import Point


@dataclass
class AudioLocation:
    distance: Point


class AudioSystem:
    def __init__(self):
        self.quest_item_normal_sound = pygame.mixer.Sound("../audio/sfx_coin_single2.wav")
        self.quest_item_high_sound = pygame.mixer.Sound("../audio/sfx_coin_single2-high.wav")
        self.quest_item_low_sound = pygame.mixer.Sound("../audio/sfx_coin_single2-low.wav")
        self.channel = pygame.mixer.find_channel()

        # Windows TTS speaker
        self.Speaker = win32com.client.Dispatch("SAPI.SpVoice")
        # don't block the program when speaking. Cancel any pending speaking directions
        self.SVSFlag = 3  # SVSFlagsAsync = 1 + SVSFPurgeBeforeSpeak = 2
        self.Speaker.Voice = self.Speaker.getVoices('Name=Microsoft Zira Desktop').Item(0)

    def play_locations(self, audio_locations: list[AudioLocation]):
        no_locations = len(audio_locations) == 0
        # stop playing item nearness sound if no objects are detected in range
        if no_locations:
            self.channel.stop()
            return

        for audio_tile in audio_locations[:1]:
            distance_x = audio_tile.distance.x
            distance_y = audio_tile.distance.y

            if distance_y > 0:
                sound = self.quest_item_low_sound
            elif distance_y < 0:
                sound = self.quest_item_high_sound
            else:
                sound = self.quest_item_normal_sound

            if distance_x > 0:
                volume = (0, 1/(distance_x + 1 + abs(distance_y)))
            elif distance_x < 0:
                volume = (1/(abs(abs(distance_x) + abs(distance_y)) + 1),0)
            else:
                volume = (1 / (abs(distance_y) + 1), 1 / (abs(distance_y) + 1))

            if self.channel.get_sound() != sound:
                self.channel.play(sound, -1)
                self.channel.set_volume(*volume)

            self.channel.set_volume(*volume)

