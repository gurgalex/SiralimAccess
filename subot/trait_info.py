import csv

from importlib import resources
from dataclasses import dataclass, field
from typing import Union



@dataclass(eq=True, frozen=True)
class CreatureLimited:
    """Limited creature info when OCR is performed on summoning/bestiary"""
    name: str
    trait: str
    trait_description: str


@dataclass(eq=True, frozen=True)
class Creature:
    name: str
    race: str = field(compare=False)
    klass: str = field(compare=False)
    health: str = field(compare=False)
    attack: str = field(compare=False)
    intelligence: str = field(compare=False)
    defense: str = field(compare=False)
    speed: str = field(compare=False)
    sources: str = field(compare=False)
    trait: str = field(compare=False)
    trait_material: str = field(compare=False)
    trait_description: str = field(compare=False)


CreatureInfo = Union[Creature, CreatureLimited]


class TraitData:
    def __init__(self):
        self.data_creature: dict[str, Creature] = dict()
        with resources.open_text("subot", "creatures.csv") as creature_file:
            for row in csv.DictReader(creature_file):
                row.pop("battle_sprite")
                row.pop("total")
                creature = Creature(**row)
                self.data_creature[row["name"].lower()] = creature
        self.data_by_trait_name = dict()

        for creature in self.data_creature.values():
            self.data_by_trait_name[creature.trait.lower()] = creature

    def by_creature_name(self, creature_name: str) -> Creature:
        lower_creature = creature_name.lower()
        return self.data_creature[lower_creature]

    def by_trait_name(self, trait: str) -> Creature:
        lower_trait = trait.lower()
        return self.data_by_trait_name[lower_trait]
