from __future__ import annotations
import json
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto

import configparser
import re

from itertools import cycle
from os import PathLike
from pathlib import Path
from typing import Optional

ENCRYPTION_KEY = "QWERTY"
_UNSET = object()


class Mode(Enum):
    ENCRYPT = auto()
    DECRYPT = auto()


def encryption(input_text: str, encryption_key: str, mode: Mode):
    """Siralim Ultimate's save file encryption"""
    output = []

    # repeat the key across all of the input text
    # input = cccccccccccccc
    #  key  = QWERTYQWERTYQW

    for input_char, key_char in zip(input_text, cycle(encryption_key)):
        if mode is Mode.ENCRYPT:
            # if encrypting, add the Unicode codepoints for the input and key chars together
            out_char = chr(ord(input_char) + ord(key_char))
        else:
            # subtract the key codepoint when decrypting
            out_char = chr(ord(input_char) - ord(key_char))
        output.append(out_char)
    return ''.join(output)


match_inner_quote = re.compile(r'"(.*)"')
match_brackets = re.compile(r'\[(.*)\]')


def convert_line(line: str, mode: Mode) -> str:
    if line[0] == "\x00":
        return None
    elif line[0] == "\n":
        return None

    if matched_brackets := match_brackets.match(line):
        inner_text = matched_brackets.groups()[0]
        decoded_text = encryption(inner_text, ENCRYPTION_KEY, mode)
        return f"[{decoded_text}]\n"
    else:
        try:
            key, value = line.split("=")
        except ValueError as e:
            print(f"no equal sign where should be: {line}")
            raise e
        decoded_key = encryption(key, ENCRYPTION_KEY, mode)
        match = match_inner_quote.match(value)
        if match:
            inner_quote = match.groups()[0]
            decoded_val = encryption(inner_quote, ENCRYPTION_KEY, mode)
        else:
            decoded_val = ''
        return f'{decoded_key}="{decoded_val}"\n'


def decode_encode_save(text: list[str], mode: Mode) -> str:
    decoded_text = []
    for line in text:
        decoded_line = convert_line(line, mode)
        if not decoded_line:
            continue
        decoded_text.append(decoded_line)
    joined = ''.join(decoded_text)
    return joined


def encrypt(decrypted_data: list[str]) -> str:
    return decode_encode_save(decrypted_data, Mode.ENCRYPT)


def decrypt(encrypted_data: list[str]) -> str:
    return decode_encode_save(encrypted_data, Mode.DECRYPT)


class MyConfigParser(configparser.ConfigParser):
    def get(self, section, option, *args, **kwargs):
        val = configparser.ConfigParser.get(self, section, option, *args, **kwargs)
        return val.strip('"')

    def getint(self, section, option, *, raw=False, vars=None,
               fallback=_UNSET, **kwargs):
        val = self.get(section, option, raw=raw, vars=vars,
                              fallback=fallback, **kwargs)
        return int(val)

    def getboolean(self,section, option, *, raw=False, vars=None,
               fallback=_UNSET, **kwargs) -> bool:
        return bool(self.get(section, option, raw=raw, vars=vars,
                              fallback=fallback, **kwargs))

    def getfloat(self, section, option, *, raw=False, vars=None,
               fallback=_UNSET, **kwargs) -> float:
        return float(self.get(section, option, raw=raw, vars=vars,
                              fallback=fallback, **kwargs))

    def set(self, section, option, value=None):
        # quote all values
        if value is None:
            val = ""
        else:
            val = f'"{value}"'
        super(MyConfigParser, self).set(section, option, val)


def split_into_dict(data) -> dict:
    new_d = defaultdict(dict)
    for k, v in data.items():
        decoration_id, keyword = k.split("|")
        new_d[decoration_id][keyword] = v
    return new_d


class DecorationMapping(Enum):
    SPAWN_POINT = (87, "Spawn Point")
    EVERETT = (122, "Project NPC(Everett)")
    SIRALOPOLY_DWARF = (279, "Siralopoly NPC(Spicy) Green")
    KENO_DWARF = (278, "Keno NPC(Sleezy) Blue")
    SCRATCH_CARD_DWARF = (280, "Scratch Card NPC(Frisky) Pink")
    SLOT_MACHINE_DWARF = (277, "Slot Machine NPC(Stinky) Red")
    COURT_JESTER = (882, "The Court Jester")
    ARENA = (357, "Arena")
    BLACKSMITH_NPC = (261, "Blacksmith NPC")
    CHAOS_GUILD = (1296, "Chaos Guild")
    DEATH_GUILD = (1297, "Death Guild")
    LIFE_GUILD = (1298, "Life Guild")
    NATURE_GUILD = (1299, "Nature Guild")
    SORCERY_GUILD = (1300, "Sorcery Guild")
    ENCHANTER_NPC = (262, "Spell Gem NPC")
    FUSION_DEVICE = (275, "Fusion Lab (maybe NPC as well?)")
    GATE_OF_THE_GODS = (269, "Gate of the Gods")
    GOBLET_OF_TRIALS = (268, "Goblet of Trials")
    MAILBOX = (980, "Mailbox")
    MENAGERIE = (274, "Menagerie(Nortah device, offset NPC needed)")
    NETHER_BOSS_SHOP = (1100, "Nether Boss Shop(Nethermancer Ned)")
    PORTAL_BLUE = (317, "Portal(Blue)")
    PORTAL_YELLOW = (321, "Portal(Yellow)")
    PORTAL_RED = (320, "Portal(Red)")
    PORTAL_GREEN = (318, "Portal(Green)")
    PORTAL_PURPLE = (319, "Portal(Purple)")
    REFINERY = (266, "Refinery")
    RELIQUARY = (271, "Reliquary")
    SUMMONING_BRAZIER = (392, "Summoning Brazier")
    TELEPORTATION_SHRINE = (273, "Teleportation Shrine")
    TOME_OF_CREDITS = (1266, "Tome of Credits")
    WARDROBE = (276, "Wardrobe")
    UNKNOWN = (999999, "UNKNOWN DECORATION")

    _ignore_ = "lookup_by_id"

    lookup_by_id: dict[int, DecorationMapping] = {}

    def __init__(self, decoration_id, decoration_name):
        self.decoration_id = decoration_id
        self.decoration_name = decoration_name


DecorationMapping.lookup_by_id = {x.decoration_id: x for x in DecorationMapping}


@dataclass
class Decoration:
    d: int
    # h: int
    # v: int
    x: int
    y: int
    kind: DecorationMapping = DecorationMapping.UNKNOWN


def load_from_file(save_slot: PathLike) -> Save:
    with Path(save_slot).open() as f:
        decrypted_data = decrypt(f.readlines())
    return Save(decrypted_data=decrypted_data)


class Save:
    def __init__(self, decrypted_data: str):
        config = MyConfigParser()
        config.optionxform = str
        config.read_string(decrypted_data)
        self.config = config

        self._castle_decorations: Optional[dict[DecorationMapping, list[Decoration]]] = None


    def castle_name(self) -> str:
        return self.config.get('Player', "CastleName")

    @property
    def castle_decorations(self) -> dict[DecorationMapping, list[Decoration]]:
        if not self._castle_decorations:
            self._castle_decorations = self.decode_castle_decorations()
        return self._castle_decorations

    def decode_castle_decorations(self):
        decorations = self.config.get("Decorations", "String")
        json_decorations = json.loads(decorations)
        raw_decorations = split_into_dict(json_decorations)

        decorations_by_type = defaultdict(list)
        for k, v in raw_decorations.items():
            _x = int(v["x"]) // 32
            _y = int(v["y"]) // 32
            _d = int(v["d"])

            try:
                decoration_type = DecorationMapping.lookup_by_id[_d]
                decorations_by_type[decoration_type].append(Decoration(x=_x, y=_y, d=_d, kind=decoration_type))
            except KeyError:
                decorations_by_type[DecorationMapping.UNKNOWN].append(Decoration(x=_x, y=_y, d=_d))
        return decorations_by_type
