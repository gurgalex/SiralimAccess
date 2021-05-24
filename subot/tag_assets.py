from __future__ import annotations

from pathlib import Path
from typing import List

import toml
from dataclasses import dataclass, Field, field

altar_mapping = {
    "Aeolian", "Apocranox", "Aurum", "Azural", "Erebyss", "Friden", "Gonfurian", "Lister", "Meraxis", "Mortem",
    "Perdition", "Regalis", "Surathli", "Tartarith", "Tenebris", "Torun", "Venedon", "Vertraag", "Vulcanar", "Yseros",
    "Zonte",
}

god_to_realm_mapping = {
    "Aeolian": "Unsullied Meadows",
    "Apocranox": "Blood Grove",
    "Aurum": "Temple of Lies",
    "Azural": "Frostbite Caverns",
    "Erebyss": "Path of the Damned",
    "Friden": "Dead Ships",
    "Gonfurian": "Kingdom of Heretics",
    "Lister": "Faraway Enclave",
    "Meraxis": "The Swamplands",
    "Mortem": "Titan's Wound",
    "Perdition": "Sanctum Umbra",
    "Regalis": "Arachnid Nest",
    "Surathli": "Azure Dream",
    "Tartarith": "Torture Chamber",
    "Tenebris": "Bastion of the Void",
    "Torun": "Cutthroat Jungle",
    "Venedon": "Caustic Reactor",
    "Vertraag": "Eternity's End",
    "Vulcanar": "Great Pandemonium",
    "Yseros": "The Barrens",
    "Zonte": "Refuge of the Magi",
}

realm_to_god_mapping = {v:k for k,v in god_to_realm_mapping.items()}

short_realm_spellings = {
    "Temple ": "Temple of Lies",
    "Refuge ": "Refuge of the Magi",
    "Azure ": "Azure Dream",
    "Bastion": "Bastion of the Void",
    "Reactor ": "Caustic Reactor",
    "Pandemonium ": "Great Pandemonium",
    "Heretics ": "Kingdom of Heretics",
    "Swamplands ": "The Swamplands",
}

@dataclass
class Asset:
    path: Path
    short_name: str = field(init=False)
    long_name: str = field(init=False)

    item_type: str = field(init=False)
    is_quest_item: bool = field(init=False, default=False)
    realm: str = field(init=False, default=None)
    is_floor_tile: bool = field(init=False, default=False)
    is_global_realm_item: bool = field(init=False, default=False)
    is_project_item: bool = field(init=False, default=False)

    @staticmethod
    def guess_from_file_layout(path: Path) -> Asset:
        pass

    @classmethod
    def from_toml(cls, toml_path: Path, asset_path: Path):
        toml.load(toml_path)


    def as_dict(self):
        d = dict()
        d["short_name"] = self.short_name
        d["long_name"] = self.long_name
        d["realm"] = self.realm
        d["item_type"] = self.item_type
        d["is_quest_item"] = self.is_quest_item
        d["is_floor_tile"] = self.is_floor_tile
        d["is_global_realm_item"] = self.is_global_realm_item
        d["is_project_item"] = self.is_project_item
        return d

    def __post_init__(self):


        if self.is_realm_altar():
            self.short_name = "Altar"

            god = self.altar_is_for_which_god()
            if god.endswith("s"):
                self.long_name = f"{god}' Altar"
            else:
                self.long_name = f"{god}'s Altar"
            self.item_type = "Altar"
            self.realm = self.altar_realm()
            self.is_quest_item = True

        elif self.is_breakable():
            self.short_name = "Breakable"
            self.long_name = self.path.stem.split("-frame")[0]
            self.item_type = "Breakable"
            self.realm = self.realm_found_in()
            self.is_quest_item = True
        elif self.is_treasure_chest():
            self.short_name = "Chest"
            self.long_name = self.path.stem.split("-frame")[0]
            self.item_type = "Chest"
            self.realm = self.realm_found_in()
            self.is_quest_item = True

        elif self.is_resource_node():
            self.short_name = "Resource Node"
            self.long_name = self.path.stem.split("-frame")[0]
            self.item_type = "Resource Node"
            self.realm = self.realm_found_in()
            self.is_quest_item = True
        elif self._is_floor_tile():
            self.short_name = "Floor Tile"
            self.long_name = self.path.stem.split("-frame")[0]
            self.item_type = "Floor Tile"
            self.realm = self.realm_found_in()
            self.is_quest_item = False
            self.is_floor_tile = True

        elif self.is_wall_tile():
            self.short_name = "Wall"
            self.long_name = self.path.stem
            self.item_type = "Wall"

        else:
            self.tag_realm_item_default()
            try:
                self.item_type
            except AttributeError:
            # If no item type was assigned
                self.item_type = "generic"


    def tag_realm_item_default(self):
        self.short_name = self.path.stem.split("-frame")[0]
        self.long_name = self.short_name

        if "plants" in self.path.parent.name:
            self.item_type = "Plant"
        elif "statues" in self.path.parent.name:
            self.item_type = "Statue"
        elif "utility-npcs" in self.path.parent.name:
            self.item_type = "Utility-NPC"
            if "Teleportation Shrine" in self.path.name:
                self.is_global_realm_item = True
            return

        for realm in god_to_realm_mapping.values():
            if realm in self.path.stem:
                self.realm = realm
        for shortened_name, realm_name in short_realm_spellings.items():
            if shortened_name in self.path.stem:
                self.realm = realm_name

        if self.realm is None:
            raise AssertionError(f"Unable to determine realm for {self.path.stem}")





    def realm_found_in(self):
        if self.item_type == "Altar":
            return self.altar_realm()
        elif self.item_type == "Breakable":
            return self.breakable_realm()
        elif self.item_type == "Chest":
            return self.treasure_realm()
        elif self.item_type == "Resource Node":
            return self.resource_node_realm()
        elif self.item_type == "Floor Tile":
            return self.floor_tile_realm()

    def floor_tile_realm(self):
        for realm_name in realm_to_god_mapping.keys():
            if realm_name in self.path.stem:
                return realm_name

    def resource_node_realm(self):
        for realm in god_to_realm_mapping.values():
            if realm in self.path.stem:
                return realm


    def is_realm_altar(self) -> bool:
        return "Realm Altar" in self.path.stem

    def is_wall_tile(self) -> bool:
        return " Wall" in self.path.stem

    def altar_realm(self):
        god = self.altar_is_for_which_god()
        return god_to_realm_mapping[god]

    def altar_is_for_which_god(self) -> str:
        for altar_name in altar_mapping:
            if altar_name in self.path.stem:
                return altar_name

    def is_breakable(self) -> bool:
        return "Breakable" in self.path.stem

    def is_resource_node(self):
        return "Resource Node" in self.path.stem

    def breakable_realm(self) -> str:
        for realm in god_to_realm_mapping.values():
            if realm in self.path.stem:
                return realm

    def is_treasure_chest(self) -> bool:
        return "Treasure Chest" in self.path.stem

    def _is_floor_tile(self) -> bool:
        return "Floor Tile" in self.path.stem

    def treasure_realm(self) -> str:
        for realm in god_to_realm_mapping.values():
            if realm in self.path.stem:
                return realm


quest_to_item_mapping = {
    "God Of The Hunt": "Gonfurian's Altar",
}

ct = 0
for asset_path in Path("../assets_padded/").glob("**/**/*.png"):
    try:
        asset = Asset(path=asset_path)
        toml_fields = asset.as_dict()
        # print(toml.dumps(toml_fields))
        toml_path = Path("../asset_tomls").joinpath(asset_path.relative_to("assets_padded"))
        toml_path = toml_path.with_suffix(".toml")
        toml_path.parent.mkdir(parents=True, exist_ok=True)
        toml_path.touch()
        toml.dump(toml_fields, toml_path.open(mode="w+"))
        print(toml.dumps(toml_fields))
        if asset.is_floor_tile:
            print(toml_path)
        ct += 1
    except AssertionError as e:
        print(e)
        continue


print(f"{ct=}")