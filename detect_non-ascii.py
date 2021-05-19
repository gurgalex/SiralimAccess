from pathlib import Path
from dataclasses import dataclass

@dataclass
class TypoReplacement:
    err_snip: str
    replacement: str

ct = 0
for path in Path("assets_padded/").glob("*/*.png"):
    try:
        path.as_posix().encode("ascii")
        err_snips = [TypoReplacement(err_snip="{", replacement="("),
                     TypoReplacement(err_snip="}", replacement=")"),
                     ]
        for err_snip in err_snips:
            if err_snip.err_snip in path.stem:
                print(f"original path: {path}")
                replacement_path = path.with_stem(path.stem.replace(err_snip.err_snip, err_snip.replacement))
                path.rename(replacement_path)

                print(f"replacement path: {replacement_path}")

    except UnicodeEncodeError:
        ct += 1
        print(f"{path.as_posix()}")

        err_snips = [TypoReplacement(err_snip="â€™", replacement="'")]
        for err_snip in err_snips:
            if err_snip.err_snip in path.stem:
                replacement_path = path.with_stem(path.stem.replace(err_snip.err_snip, err_snip.replacement))
                path.rename(replacement_path)

                print(f"replacement path: {replacement_path}")


print(f"non-ascii filenames: {ct}")