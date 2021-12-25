# Siralim Access

A program to aid in making [Siralim Ultimate](https://store.steampowered.com/app/1289810/Siralim_Ultimate/) more accessible to visually impaired users.

## Demo

[![Siralim Access Video Demo of Realm Navigation and TTS](https://img.youtube.com/vi/00jdY_b_ra0/maxresdefault.jpg)](https://www.youtube.com/watch?v=00jdY_b_ra0)


## Features
- Integration with your screen reader of choice
  - NVDA
  - JAWS
  - Window-Eyes
  - SuperNova
  - System Access
  - ZoomText
- Sound list screen to familiarize with which sounds are for what
- Unique audio sounds for specific items
- Replaces game font with accessible version (Arial bold)
- Speaks the currently selected menu item
- Dialog boxes are spoken such as for the story, NPCs, and realm altars
- Specialized output for certain UI screens
  - Summoning brazier
  - Creatures screen (know which creature's traits, artifact, spell gems are being configured)
  - Reorder creature screen
  - GodForge avatar select
  - Teleportation Shrine realm select
  - Wardrobe in castle
  - Inspect UI screen
  - Field Items UI

## Item sounds
[video of sounds playing](https://youtu.be/2vVCJtCocbA)

- Quest items
- Project items
- Realm altar
- NPC
- Nether portal and portal exits
- Creature Master
- Chest
- Divination Candle
- Teleportation shrine
- Treasure Map
- Summoning brazier
- Pandemonium shrine
- Riddle dwarf
- Exotic Portal
- Emblem
- Castle
- - Wardrobe
- - Blacksmith
- - Enchanter
- - Everett

## Keyboard Shortcuts
| Action                    | Default Key |
| ------------------------- | ----------- |
| Speak secondary info      | o           |
| Speak all available info  | v           |
| Copy all available info   | c           |
| Edit config file | C |
| speak help text | ? |
| EXPERIMENTAL: OCR of text to the right of menu selection | O |

## Requirements

### Game settings
- Display Zoom: 1x - to identify any realm object

### Operating System Requirements
- Windows 10 - only so far tested on 2021 releases
- The English United States language pack must be installed [Instructions can be found here](https://support.microsoft.com/en-us/windows/install-a-language-for-windows-ccd853d3-9ecd-7da7-9ef0-72b4a055410a)

## How to download
The latest version of the installer can be found [here https://github.com/gurgalex/SiralimAccess/releases/latest](https://github.com/gurgalex/SiralimAccess/releases/latest)

## FAQ
## How to change the voice used if not using a screen reader?
The SAPI voice is controlled by the Windows control panel.
- Control Panel -> Speech Recognition -> Text to Speech -> Voice selection

## Where is the config file?
`%localappdata%\SiralimAccess`
Edit `config.ini`
