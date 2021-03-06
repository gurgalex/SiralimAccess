## v0.15.0
### feat
- add many spell gem UI screens. All speak spell name, and class.
  - battle
    - cast
      - spell gem class and ethereal status, and description are available in the cast battle screen now
  - refinery
    - grind spell gem
  - manage spell gems on your creatures
    - will speak class, whether it is the default, and speak when you change the creature page
    - spell gem equip interface when managing spell gems
  - enchanter
    - craft
    - enchant
      - will speak number of properties and if you can't enchant anymore at the end of each enchant name on 1st UI change
    - disenchant
      - will tell if the spell gem is already fully disenchanted.
    - upgrade
    - codex - spells

## v0.14.2
### feat
- read Field Items UI creature selection

## v0.14.1
### feat
- Inspect UI screen
### fix
- The 2nd quest should read its description now

# v0.14.0
## fix
- The hang monitor has been replaced with a crash handler. This should work much better on low-end computers
## feat
- Added an option to disable speaking any text OCR -> enabled, set to False
- Added new realm sounds
  - Add realm sound for emblems on the ground
  - Add realm sound for divination candle
- Castle sounds
  - Add wardrobe castle sound
  - Add blacksmith castle sound effect
  - Add enchanter castle sound effect
  - Add everett castle sound effect
- UI screen
  - anointment claim from false god

# v0.13.1
## fix
- crash on Perk screen

# v0.13.0
## feat
- All 9 new realms supported
- 62 new realm quests from the 9 new realms

## fix
- multi-line quests now are detected correctly
- creature HP in-battle should no longer be misidentified as dialog text

# v0.12.6
## feat
- Add treasure map sound effect
- Add exotic portal sound effect

# v0.12.5
## feat
- Add pandemonium shrine sound effect

# v0.12.4
## fix
- missing riddle dwarf SFX

# v0.12.2
## fix
- Crash when fail to detect realm instability
## feat
- Add riddle dwarf sound effect

# v0.12.1
## fix
- reintroduce check for English US language pack

# v0.12.0
## change
- help text is now only spoken whenever a UI screen is opened/reopened. Press ? to hear it again at any time
- Text should be less jumbled when icons are present
- There is now a pause between sections of text

## feat
- Add experimental OCR option (uppercase O) to read text that is to the right of any green text
  - Press uppercase O to force the text to the right to be read
  - Seems to cover most boxes, however, the text is sometimes very verbose with lots of unneeded info
  - This is a stopgap measure until areas are identified for each UI screen
- New quest sound. Hopefully it is less annoying.
- The config file for Siralim Access can now be opened by pressing uppercase C. Siralim Access must still be closed for changes to take effect.
- Add more UIs
  - Perk screen
  - Codex screens
    - Most of the reference list screens
    - Game Information - Only the nether boss screen


# v0.11.2
## fix
- Crash when Creatures screen would pop up a dialog box
- Crash on summoning screen if no existing trait or creature name was found
- Fix for mod crashing with low-end computers taking long to startup new processes

## features
- Add more dedicated UI screens
  - Teleportation Shrine Realm Select UI

# v0.11.1
## fix
- fix rapid repeat audio of realm object detection

# v0.11.0
## feat
- Certain UI Screens now give more helpful output
  - Summoning Brazier - Reads current creature, read trait + description, copy all creature info to clipboard
  - Creatures screen - Now tells what creature number is being interacted with for example Creature 1 Trait(s)
  - GodForge select - Tells what creature is being selected to GodForge
  - Reorder Creatures - Tells what creature you are selecting, and which number to swap it with

## perf
- CPU usage should be ~15-20% lower due to only scanning quests every second

## fix
- Better, Faster, Stronger, Dead quest. Phase Folk killed now works (typo in quest name)
- Key presses are no longer read when Siralim Ultimate is the active window

## Change
- Default to not repeat sounds when stationary for new installations. Delete config.ini or set `repeat_sound_when_stationary` to false.

# v0.10.3
# fix
- Fix broken release by pinning opencv dependency version
# v0.10.2
## feat
- Add nether portal sound and same sound for portal exit
- Add summoning brazier sound effect (fire crackling)

# v0.10.1
## Fix
- Program no longer crashes if offline when checking for updates

# v0.10.0
## change
- Reading NPC dialog boxes must now be done manually with the `o` key. The program will till you if there is a dialog box to read
  - This is only the case when a menu selection such as when talking to the blacksmith is present
  - Story and popup dialog boxes will still be read automatically
## feat
- Text to Speech now integrates with your screen reader. If no screen reader is found Microsoft Speech API (SAPI) will be used as a fallback.
- Added keyboard shortcuts to read the dialog box (default o), and reread the selected menu item (default m).
- An update check is now performed when launched. If you would not like your web browser to open the download page, set `update_popup_browser` to false
# v0.9.28
## feat
- Speak if the required English language pack is not installed on the system
# v0.9.27
# fix
- Attempt yet another fix for sporadic startup crashes

#v0.9.26
# feat
- The SAPI voice is now controlled by the Windows control panel.
  - Go to Control Panel -> Speech Recognition -> Text to Speech -> Voice selection
# fix
  - dialog boxes and menu selections should now be spoken and stop speaking when closed now
#v0.9.25
# perf
- Pause object detection, OCR, and frame capture when Siralim Ultimate is minimized and/or in the background
  - This drops CPU usage to near 0% when not needing to do any analysis
# fix
  - Unsupported quest notification was broken in the last update. Now speaks it
#v0.9.24
# feat
- Story and NPC dialog boxes are now spoken

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
