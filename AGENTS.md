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

# Ableton logs
tail -100 "/Users/shangyuhsu/Library/Preferences/Ableton/Live 11.3.43/Log.txt"
tail -f "/Users/shangyuhsu/Library/Preferences/Ableton/Live 11.3.43/Log.txt"

# Firmware logs
cat /dev/cu.usbmodem162330301

## Guidance
When implementing the python control surface script, always reference MIDIRemoteScripts/Push to see how Ableton Push implements things


## `MPK249_Flow/` + `mpk249_control/` — Akai MPK249 Port A in Live

A remote script and a Max for Live device, split so behaviour can change without restarting Live.

- **`MPK249_Flow/`** (remote script; linked into Live's `MIDI Remote Scripts` like `cubefish`): the factory MPK249 script's transport, faders (track volumes) and switches (arm), plus Port A's 16 pads (USB A1, notes 36-51, pad 1 bottom left) and 8 knobs (USB A1, CC 22-29, Inc/Dec 2) as named controls `Pad_1..16`, `Encoder_1..8`. It only *claims* those: a listener of its own on each makes Live forward the message to the script, and a forwarded message never reaches a track. Live: Control Surface `MPK249_Flow`, input `MPK249 (Port A)`, output `MPK249 (Remote)` - the Remote port is the only one that takes the pad-colour SysEx.
- **`mpk249_control/`** (Max for Live audio effect, for the master track; `python3 build.py --install`): `mpk249.js` finds the script among `control_surfaces`, grabs its controls and observes their values; what each does is the table at its top. Live's API covers track select/mute/solo/arm, metronome, mixer, `scroll_view`/`zoom_view`. It does not cover the arrangement grid, plug-in windows or scrolling a view without moving the selection, so `mpk249-keys.js` (Node for Max) posts those as keystrokes/scroll events through `mpk249-events.jxa` (one long-lived `osascript -l JavaScript`; needs Accessibility permission). Bank A pad colours are menus in the device, written via the script's `send_midi` as `F0 47 00 24 31 00 13 10 <addr hi> <addr lo> <16 codes> F7` - Off colours at 0x57C, On at 0x5BC (bank B: 0x58C / 0x5CC; Flow writes those).
- Installed scripts are symlinks into this repo, and `autowatch` / `@watch` reload them on save.
