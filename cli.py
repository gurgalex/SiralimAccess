import os
import sys
from pathlib import Path
import shutil

import click

OCR_FONT = 'arialbd.ttf'
FONT_FILE_ORIG_SIRALIM_ULTIMATE = Path("C:\Program Files (x86)\Steam\steamapps\common\Siralim Ultimate\Eight-Bit-Dragon2.otf")
ORIGINAL_BACKUP_FONT_FILEPATH = FONT_FILE_ORIG_SIRALIM_ULTIMATE.parent.joinpath("Eight-Bit-Dragon2-orig.otf")


@click.group()
def enter_cli():
    pass


@enter_cli.command()
def install():
    win_dir = os.environ["windir"]
    font_filepath = Path(win_dir).joinpath("Fonts").joinpath(OCR_FONT)
    if not font_filepath.exists():
        raise Exception(f"OCR font does not exist in system: {font_filepath.as_posix()}")
    # backup original
    if ORIGINAL_BACKUP_FONT_FILEPATH.exists():
        print(f"Original font already backed up since {ORIGINAL_BACKUP_FONT_FILEPATH.name} exists")
    else:
        shutil.copy(FONT_FILE_ORIG_SIRALIM_ULTIMATE,ORIGINAL_BACKUP_FONT_FILEPATH)

    shutil.copy(font_filepath, FONT_FILE_ORIG_SIRALIM_ULTIMATE)
    print(f"{font_filepath.name} has replaced {FONT_FILE_ORIG_SIRALIM_ULTIMATE.name}")

@enter_cli.command()
def restore():
    print("entered restore")
    # backup original
    if not ORIGINAL_BACKUP_FONT_FILEPATH.exists():
        print(f"Original game font backup is missing. Should have been here: {ORIGINAL_BACKUP_FONT_FILEPATH.name}")
        sys.exit(2)
    else:
        shutil.copy(ORIGINAL_BACKUP_FONT_FILEPATH, FONT_FILE_ORIG_SIRALIM_ULTIMATE)

    # delete the backup
    ORIGINAL_BACKUP_FONT_FILEPATH.unlink()
    print(f"{FONT_FILE_ORIG_SIRALIM_ULTIMATE.name} restored")



if __name__ == "__main__":
    # needed to prevent infinite process spawns when using pyintaller
    import multiprocessing
    multiprocessing.freeze_support()
    import sentry_sdk
    from subot.main import start_bot, before_send

    sentry_sdk.init(
        "https://90ff6a25ab444640becc5ab6a9e35d56@o914707.ingest.sentry.io/5855592",
        traces_sample_rate=1.0,
        before_send=before_send,
    )
    if len(sys.argv) == 1:
        start_bot()
    else:
        enter_cli()