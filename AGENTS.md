## What this project is

A **custom Ableton Live MIDI Remote Script** (`cubefish`) paired with **USB-MIDI firmware** on a Teensy-class board (`live_controller`). Live maps device parameters to encoders; the script sends **SysEx** so each encoder’s OLED shows name/value, and the hardware sends **CC** messages back for parameter changes and bank buttons.

## Top-level directories

### `cubefish/`

**Ableton Live Remote Script** (Python, Live’s embedded runtime — typically v2 `_Framework` + v3 `ableton.v3` mix as in stock scripts).

| File | Role |
|------|------|
| `__init__.py` | Entry point: `get_capabilities()`, `create_instance()` — must match your USB device’s vendor/product IDs for Live to load the script. |
| `Arduino.py` | Main `ControlSurface`: device banking, bank buttons, `CustomEncoderElement` instances, SysEx for bank labels on the hardware. |
| `encoder.py` | `CustomEncoderElement`: builds knob SysEx (display text + MIDI value sync byte; tag must match firmware). |
| `bank_definitions.py` | Per-device bank layouts (merges with / overrides Live defaults for specific devices). |
| `elements.py`, `mappings.py`, `midi.py`, `util.py` | Elements, routing helpers, MIDI constants, logging. |

**Firmware** (Arduino/Teensy): multiplexed encoders and buttons, **SSD1306** displays over I2C muxes, **USB MIDI** in/out.

| File | Role |
|------|------|
| `live_controller.ino` | Main loop: read encoders/buttons, send CC; receive SysEx from Live and update `display_text` / `button_text` / encoder sync. |
| `const.h` | Pin mux map, encoder/switch counts, debounce constants, `EncoderActionByState` table. |

Hardware details (pinout, display routing) live in `const.h` and the `.ino` file — change protocol or layout in **both** firmware and `cubefish` if you change messages.

### `MIDIRemoteScripts/` (optional)

This is a **reference tree** (e.g. decompiled or extracted Live factory Remote Scripts) to compare APIs. It is **not** loaded by Live from this repo path.

## Cross-repo rules for agents

1. **SysEx knob format** is shared: script (`encoder.py` / `KNOB_SYSEX_SYNC_TAG`) and firmware (`CUBEFISH_KNOB_SYNC_TAG` in the `.ino`) must stay aligned. USB MIDI SysEx assembly must preserve `0x00` data bytes (use Code Index handling, not “if (byte)” checks that drop zero).

2. **Bank buttons** use CC on the channel the script expects (see `Arduino.py` / firmware `controlChange` calls).
