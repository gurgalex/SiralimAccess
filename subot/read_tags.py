from collections import defaultdict
from dataclasses import dataclass, field
from typing import Set, Optional, DefaultDict
from pathlib import Path
import toml
from enum import Enum
import cv2
from numpy.typing import ArrayLike
from subot.utils import extract_mask_from_rgba_img

@dataclass(frozen=True)
class Asset:
    data: ArrayLike
    data_gray: ArrayLike
    mask: ArrayLike
    path: Path
    short_name: str
    long_name: str
    item_type: str
    phash: ArrayLike
    realm: Optional[str] = None
    is_floor_tile: bool = False
    is_global_realm_item: bool = False
    is_project_item: bool = False
    is_quest_item: bool = False
    quest_single_line_name: Optional[str] = None


class Realm(Enum):
    ARACHNID = "Arachnid Nest"
    Azure = "Azure Dream"
    BASTION = "Bastion of the Void"
    BLOOD_GROVE = "Blood Grove"
    REACTOR = "Caustic Reactor"
    TEMPLE_LIES = "Temple of Lies"

set_hashes = set()
dups = []

class AssetDB:
    def __init__(self):

        # store all possible realm objects for quick access
        data_lookup = dict()
        data_lookup["global_realm"]: list[Asset] = []
        data_lookup["realm"] = defaultdict(list)
        data_lookup["quest"] = defaultdict(list)
        data_lookup["floortile"] = defaultdict(list)
        data_lookup["all_realm_tiles"]: list[Asset] = []
        data_lookup["long_name"]: dict[str, Asset] = {}

        # Quest single line mapping to Asset decoration frames for quest
        data_lookup["quest_item"]:  dict[str, list[Asset]] = {}
        self.lookup: dict = data_lookup

        tomls_location = "asset_tomls/"
        pngs_location = "assets_padded/"
        # pngs_location = "assets/"

        phasher = cv2.img_hash.PHash_create()
        for asset_config_path in Path(tomls_location).glob("**/*.toml"):

            png_path = Path(pngs_location).joinpath(asset_config_path.relative_to("asset_tomls")).with_suffix(".png")
            data = cv2.imread(png_path.as_posix(), cv2.IMREAD_UNCHANGED)
            if data is None:
                print(f"{png_path=} not exist")
                continue
            data_gray = cv2.cvtColor(data, cv2.COLOR_BGR2GRAY)
            try:
                mask = extract_mask_from_rgba_img(data)
            except TypeError as e:
                print(e)
                raise Exception(f"{png_path.as_posix()} does not have a mask")
            phash = phasher.compute(data)
            toml_data = toml.load(asset_config_path)
            asset = Asset(data=data, data_gray=data_gray, mask=mask, path=asset_config_path, phash=phash, **toml_data)
            data_lookup["long_name"][asset.long_name] = asset
            if asset.realm and not asset.is_floor_tile:
                data_lookup["realm"][asset.realm].append(asset)
            if asset.is_global_realm_item:
                data_lookup["global_realm"].append(asset)

            is_realm_floortile = asset.realm is not None and asset.is_floor_tile
            if is_realm_floortile:
                data_lookup["floortile"][asset.realm].append(asset)
                data_lookup["all_realm_tiles"].append(asset)

            if asset.quest_single_line_name is not None:
                # raise Exception(f"No quest name assigned for: {asset.path}")
                data_lookup["quest_item"].setdefault(asset.quest_single_line_name, []).append(asset)

            self.lookup = data_lookup

    def get_floortile_for_realm(self, realm: str) -> list[Asset]:
        return self.lookup["floortile"][realm]

    def all_realm_floortiles(self) -> list[Asset]:
        return self.lookup["all_realm_tiles"]

    def get_realm_assets_for_realm(self, realm: str) -> list[Asset]:
        return self.lookup["realm"][realm]

    def get_realm_altar(self, realm):
        pass





if __name__ == "__main__":

    from time import sleep
    db = AssetDB()
    realm = db.get_realm_assets_for_realm(Realm.TEMPLE_LIES.value)
    cv2.namedWindow("Mask", cv2.WINDOW_GUI_EXPANDED)
    for idx, asset in enumerate(realm):
        cv2.imshow("Mask", asset.mask)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            cv2.destroyAllWindows()
            break
        sleep(1)
        print(f"{idx=}")




