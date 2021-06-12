

# FInding the Player
The player is found by figuring out the width and height the game window is (excluding title bar) and then drawing a 32x32 rectangle
on the center of the window.
This is because the player always stays in the same place, everything else just moves

# How game sprites are extracted

[UndertaleModTool](https://github.com/krzys-h/UndertaleModTool) is used to extract game sprites.
Load up the `data.win` file of Siralim Ultimate, and select the script `ExportAllTexturesWithPadding`.
This will take more than 15 minutes, you can see the results in the `Export_Textures` folder near `data.win`.

## Organizing the sprites after extraction
Sprites can be grouped into these categories with the following filename patterns.
* Attack animations - `anim_*.png` 64x64 dim
* NPC - `npc_*.png` 32x32 dim
* master sprite - `master_*.png` 32x32 dim
* master icon - `master_*.png` 16x16 dim
* Mimic OW - `Mimic_*_OW*.png` 32x32 dim
* Creatures overworld - `ospr_*.png` 32x32 dim
* Battle Sprites - `spr_crits_battle_*.png` 64x64 dim
* Skins - CamelCase creature name + skin name + `*_OW*.png` dim 32x32 - Example `RubyParagon_Quartz_OW_0.png`
* story boss (except Caliban) - `Boss_*.png`
* spell animations - `spe_*.png` 64x64 dim
* castle and realms sprites - `spr_*.png`
    * Unique to realm decorations have some info on all of them like `cave` for Arachnid's Nest
* Breakables - `spr_breakable_*.png` 32x32 dim
* non-generic chests - `spr_chest_*.png` 32x32 dim
* debris - `spr_debris_*.png` 32x32 dim
* Emblem - `spr_emblem_*.png` 32x32 dim
* altar - `spr_god_*.png` 32x64 dim
* realm wall - `spr_wall_*` example `spr_wall_cave` 32x32 dim
* painting - `*painting*.png`
