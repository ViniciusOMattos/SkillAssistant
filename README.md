# SkillAssistant

A keyboard automation tool with auto-aim for games, using computer vision to detect targets on the screen.

## Features

* **Key combos**: Create key sequences with custom delays
* **Profiles**: Save and load multiple combo profiles
* **Auto-aim**: Target detection using computer vision (OpenCV)

  * Template matching
  * HSV color detection
* **Batch input**: Type fast sequences (e.g., `qwer`)
* **Tkinter interface**: Simple GUI with scrolling and combo preview
* **macOS native**: Keyboard polling via Quartz API

## Structure

```
SkillAssistant/
├── main.py              # Main GUI + bot loop
├── skill_assistant.py   # Version without auto-aim
├── config.py            # Capture and target settings
├── targets.py           # Template management
├── target_predictor.py  # Position smoothing/clamping
├── detector_viewer.py   # Detection debugging
├── profiles/            # Saved profiles (.json)
└── targets/             # Target templates (.png)
```

## Installation

```bash
pip install -r requirements.txt
```

### Dependencies

* `pyautogui` - Keyboard simulation
* `opencv-python` - Computer vision
* `numpy` - Mathematical operations
* `mss` - Screen capture
* `pyobjc` - Quartz API (macOS)

## Usage

```bash
python main.py
```

### Controls

* **Hotkey**: Key that activates the combo (configurable per combo)
* **START/PAUSE**: Toggle the bot
* **+ Combo / - Combo**: Add/remove combos
* **Batch (D)**: Fast sequence input
* **Aim**: Toggle auto-aim per combo

### Profiles

Profiles are saved in `profiles/{name}.json`:

```json
{
  "name": "default",
  "combos": [
    {
      "attacks": [
        {"key": "q", "delay": 100},
        {"key": "w", "delay": 150},
        {"key": "e", "delay": 100}
      ],
      "hotkey": "z",
      "auto_aim": true
    }
  ]
}
```

## Auto-aim

The system detects targets using:

1. **Template matching** with `cv2.matchTemplate`
2. **HSV filtering** to validate target color
3. **Non-max suppression** to avoid duplicates
4. **Clamping** to smooth mouse movement

Settings in `config.py`:

* `CAPTURE_WIDTH/HEIGHT`: Central capture area
* `TARGET_OFFSET_X/Y`: Cursor offset relative to the target
* `PLAYER_OFFSET_X/Y`: Player center
* `TARGET_CONFIGS`: Thresholds per template

## Platform

* **macOS**: Native keyboard polling via Quartz API
* **Windows/Linux**: Fallback to PyAutoGUI
