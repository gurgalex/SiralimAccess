from pathlib import Path

from saver.save import Save, ConfigOptions, load_blank_save, SIRALIM_ULTIMATE_SAVE_FOLDER_WINDOWS, load_blank_config, load_config_from_fp, load_save_from_filepath, load_save_from_fp
import sys
if sys.platform == "win32":
    CONFIG_SAVE_PATH = SIRALIM_ULTIMATE_SAVE_FOLDER_WINDOWS.joinpath("config.sav")
else:
    raise NotImplementedError(f"save/config file loading not supported on {sys.platform}, only Windows supported")


class SaveMonitor:
    def __init__(self, config: ConfigOptions):
        self.save_last_modified: int = 0
        self.save_filepath: Path = SIRALIM_ULTIMATE_SAVE_FOLDER_WINDOWS.joinpath(config.last_slot)
        self.save = self._first_save_load()

    def _first_save_load(self) -> Save:
        try:
            with self.save_filepath.open() as f:
                return load_save_from_fp(f)
        except FileNotFoundError:
            return load_blank_save()

    def load_save(self):
        try:
            last_modified = self.save_filepath.stat().st_mtime

            change_since_last_check = last_modified != self.save_last_modified
            # use existing config
            if not change_since_last_check:
                return

            with self.save_filepath.open() as f:
                self.save = load_save_from_fp(f)
                self.save_last_modified = last_modified
                return
        except FileNotFoundError:
            self.save = load_blank_save()
            self.save_last_modified = 0
            return


class GameConfigMonitor:
    def __init__(self):
        self.config_last_modified: int = 0
        self.game_config = self._first_config_load()

    def _first_config_load(self) -> ConfigOptions:
        try:
            last_modified = CONFIG_SAVE_PATH.stat().st_mtime
            with CONFIG_SAVE_PATH.open() as f:
                load_config = load_config_from_fp(f)
                self.config_last_modified = last_modified
                return load_config
        except FileNotFoundError:
            return load_blank_config()

    def load_config(self):
        try:
            last_modified = CONFIG_SAVE_PATH.stat().st_mtime

            change_since_last_check = last_modified != self.config_last_modified
            # use existing config
            if not change_since_last_check:
                return

            with CONFIG_SAVE_PATH.open() as config_fp:
                self.game_config = load_config_from_fp(config_fp)
                self.config_last_modified = last_modified
                return
        except FileNotFoundError:
            self.game_config = load_blank_config()
            self.config_last_modified = None
            return
