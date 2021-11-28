from dataclasses import dataclass
from typing import Optional

import re

REPLACEMENTS = {
    '" + scr_GodName(GOD_CAVE, true) + "."': 'Regalis, Goddess of Poison.',
    '" + scr_GodName(GOD_GRASSLAND, true) + "."': "Aeolian, God of Wind.",
    '" + scr_GodName(GOD_WINTER, true) + "."': "Azural, God of Frost.",
    '" + scr_GodName(GOD_ARIAMAKI, true) + "."': "Ariamaki, God of Balance.",
    '" + scr_GodName(GOD_ALEXANDRIA, true) + "."': "Alexandria, God of Falsity.",
    '" + scr_GodName(GOD_CHAOS, true) + "."': "Vulcanar, God of Fire.",
    '" + scr_GodName(GOD_BLOODBONE, true) + "."': "Mortem, God of Blood.",
    '" + scr_GodName(GOD_AUTUMN, true) + "."': "Apocranox, God of the Hunt.",
    '" + scr_GodName(GOD_PURGATORY, true) + "."': 'Perdition, God of Extinction.',
    '" + scr_GodName(GOD_VOID, true) + "."': 'Tenebris, God of Shadow.',
    '" + scr_GodName(GOD_DEATH, true) + "."': 'Erebyss, Goddess of Darkness.',
    '" + scr_GodName(GOD_LIFE, true) + "."': 'Surathli, Goddess of Light.',
    '" + scr_GodName(GOD_DESERT, true) + "."': 'Yseros, Goddess of Illusion.',
    '" + scr_GodName(GOD_GEM, true) + "."': 'Aurum, God of Vanity.',

    # remove to allow personalized castle names
    # '" + global.castlename + "': 'Siralim',
}

GODNAME_REGEX = r"(scr_GodName.*\))"

def multiple_replace(replacements, text):
  # Create a regular expression  from the dictionary keys
  # text = re.sub(GODNAME_REGEX, '', text)
  regex = re.compile("(%s)" % "|".join(map(re.escape, replacements.keys())))

  # For each match, look-up corresponding value in dictionary
  replaced_content = regex.sub(lambda mo: replacements[mo.string[mo.start():mo.end()]], text)
  return replaced_content



with open("quest list.txt") as f:
    data = f.readlines()


qid = 0

def get_quest_name(line: str) -> str:
    quote_start = line.find(' = ') + 3
    text_end = line.find(';')
    return line[quote_start:text_end]

def perform_replacement(line):
    return multiple_replace(REPLACEMENTS, line)

def join_plus_strings(line):
    return ''.join(line.split('" "'))

@dataclass
class Quest:
    desc: Optional[str] = None
    title: Optional[str] = None
    items_needed: Optional[str] = None
    needs_manual_edit: bool = False


if __name__ == "__main__":
    quests = []
    quest_obj = Quest()
    for line in data:
        qid = -1
        if line.startswith("	qid"):
            quest_obj = Quest()
            qid += 1
        elif line.startswith("	global.quest[qid, QUEST_NAME] = "):
            quest_title = get_quest_name(line)
            quest_title = perform_replacement(quest_title)
            quest_title = join_plus_strings(quest_title)
            if '+' in quest_title:
                quest_obj.needs_manual_edit = True
            quest_obj.title = quest_title
        elif line.startswith("	global.quest[qid, QUEST_DESC] = "):
            quest_desc = get_quest_name(line)
            quest_desc = perform_replacement(quest_desc)
            quest_desc = join_plus_strings(quest_desc)
            if '+' in quest_desc:
                quest_obj.needs_manual_edit = True
            quest_obj.desc = quest_desc
        elif line.startswith('	global.quest[qid, QUEST_ITEM_NEEDED] = '):
            items_needed = get_quest_name(line)
            items_needed = perform_replacement(items_needed)
            items_needed = join_plus_strings(items_needed)
            if '+' in items_needed:
                quest_obj.needs_manual_edit = True
            quest_obj.items_needed = items_needed

        elif line.startswith("	global.quest[qid, QUEST_REPEATABLE] "):
            quests.append(quest_obj)

    ultimate_quests = []
    manual_ct = 0
    for quest in quests:
        if quest.title.startswith("scr_GodLevelWord"):
            continue
        elif quest.title.startswith('"Welcome to'):
            continue
        ultimate_quests.append(quest)
        if quest.needs_manual_edit:
            manual_ct += 1
            print(f"quest title:{quest.title} quest_desc:{quest.desc}")
    print(f"needed {manual_ct}")

    import csv
    with open("quest_title_desc.csv", "w+", newline='') as f:
        reader = csv.DictWriter(f, ['title', 'desc', 'items_needed'])
        reader.writeheader()
        for quest in ultimate_quests:
            reader.writerow({"title": quest.title, "desc": quest.desc, 'items_needed': quest.items_needed})





