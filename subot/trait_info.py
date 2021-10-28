import csv
from pathlib import Path


# file = Path("../compendium-traits.csv")

from importlib import resources
from dataclasses import dataclass
from typing import Union

trait_file = resources.open_text("subot", "compendium-traits.csv")
creature_file = resources.open_text("subot", "creatures.csv")


from dataclasses import field

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


if __name__ == "__main__":
    t = TraitData()

    new_trait_csv = []
    for row in csv.DictReader(trait_file):
        try:
            creature = t.by_trait_name(row["Trait Name"])
            row["Creature"] = creature.name
        except KeyError:
            pass
        new_trait_csv.append(row)
    keys = new_trait_csv[0].keys()
    with open('trait_compendium_full_creature_name.csv', "w+", newline='') as f:
        dict_writer = csv.DictWriter(f, keys, quoting=csv.QUOTE_ALL)
        dict_writer.writeheader()
        dict_writer.writerows(new_trait_csv)


