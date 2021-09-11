#v0.9.23
# fix
- No longer crash if Siralim Ultimate is minimized when starting up Siralim Access
- Commas should now be detected in the standard game resolution. It is now looser on what is considered white.

#v0.9.22
# fix
- Program now no longer crashes without admin privileges. Determining the font install location is now only done during the installer phase when those privileges are given.#v0.9.21
# fix
- encountering resource nodes should no longer crash the program. They were misclassified as regular sprites
- detect Siralim Ultimate install location on non-C drives. Fixes the font failing to install
- Maximizing the game (not fullscreen) now doesn't break object detection
- The game can now be resized without breaking object detection

# v0.9.20
# feat
- Many parts of the program are now configurable. A config file is generated at `%APPLOCALDATA%\SiralimAccess`.
  - OCR menu reading can be toggled or off with the `read_selected_menu` config option
  - Master and individual sound effect volumes can now be adjusted from 0-100%
  - You can now choose if you'd like the detected object sounds to turn off when you have not moved for a period of time
    - `repeat_sound_when_stationary` and duration with `repeat_sound_seconds`

  - The program menu can be disabled with the `show_ui` config option
- Torture Chamber, Kingdom of Heretics, and Where the Dead Ships Dwell realms should have much better support now.
# perf
- object detection is now much more responsive and no longer lags after enemy encounters
- OCR of menu entries is now slightly faster, frequency of scanning can be adjusted with `whole_window_fps`

## v0.9.19
# fix
- See if enabling console mode allows screenshots for some users

## v0.9.18
# fix
- Application would stop responding if no screenshot data was captured or game is minimized
- Downgrade python executable generator to hopefully prevent from being falsely flagged as a virus

## v0.9.17
- Report version when sending remote error logs

## v0.9.16
# fix
- Make sure certain versions of dependencies are installed to prevent initial launch crashes

## v0.9.14
# feature
- Speak the selected menu item in green text
# performance
- Use native Windows 10 OCR instead of Tesseract OCR

## v0.9.13
### Performance
- Long realm scanning only happens if the previous realm hasn't been found for a bit
    - Should help with some realm corridors causing lag spikes when moving

## v0.9.12
### feat
- A console no longer shows up alongside the Siralim Access window

## v0.9.11
### Feat
- Add Quest "Cast Away"
- Add Chest detection sound
- Add Sound demo UI screen

### Fix
- Resource node quests now work correctly

## v0.9.10 (2021-07-23)

### Fix

- Add support for all resource nodes
- Generic Fetch Quest is unsupported

## v0.9.9 (2021-07-22)

### Feat

- increase scanning from 6 -> 8 tiles from player

### Fix

- No longer misdetects minimizing as being fullscreen
- App wouldn't work if DPI scaling > 100%
- postinstall launch of Access now closes installer

## v0.9.8 (2021-07-22)

### Feat

- have the setup default to install for all users
- add install/uninstall support for OCR font

### Refactor

- move app build and metadata to one place

## v0.9.7 (2021-07-20)

### Perf

- 1/3 CPU usage. Reduced near scanning from 60 -> 20 FPS
