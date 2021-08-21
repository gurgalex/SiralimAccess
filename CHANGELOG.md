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
