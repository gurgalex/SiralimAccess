import csv
from sqlalchemy.exc import IntegrityError
from data_entry_quests import update_quest_desc

if __name__ == "__main__":

    with open("quest_title_desc.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            quest_title = row["title"]
            quest_title = quest_title.strip('"')
            description = row["desc"]
            description = description.strip('"')
            try:
                update_quest_desc(title=quest_title, description=description)
            except IntegrityError:
                pass
