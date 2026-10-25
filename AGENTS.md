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
- Live behaviours behind choices in `mpk249.js`: `scroll_view` on the Arranger is the arrow keys - left/right move the insert marker by the grid (Shift: grow the selection), up/down move it to the next track at the same time, which is how track pads take the cursor with them; but with the **loop brace selected the arrows move the loop**, so the cursor knob can instead move the start marker (`current_song_time`), which never touches it. Setting `selected_track` alone leaves the insert marker on the old track. Cmd-Alt-P shows/hides plug-in windows that have been opened; it does not open one, and Live 11's API has no call that does. Keystrokes are typed with real modifier key events - flags on the key event alone did not register Cmd-Alt-P.
- The view knobs (cursor, side scroll, zoom) count detents - one message is one detent, acceleration ignored - and act once per N (the device's numboxes); the mixer knobs keep acceleration.

## `Launchkey_Flow/` — keeps the Launchkey MK4 61's Custom 1 out of Live's tracks

Custom 1 (Components: pads notes 36-51, encoders CC 21-28 relative, all channel 15) is Flow's - Flow reads and lights it over its own CoreMIDI connection. Custom Modes can only send on the keys port, which Live must listen to for the keys, so this script claims those 24 messages (a listener of its own on each; a forwarded message never reaches a track) and does nothing else. Live: a control-surface row of its own, input the Launchkey's keys port ("Launchkey MK4 61 (MIDI)"), output None - Ableton's Launchkey MK4 script keeps its own row on the DAW ports, untouched. No controller id, so Live never auto-assigns it. Linked into Live's MIDI Remote Scripts like `cubefish`.

## `Axiom_Flow/` — the M-Audio Axiom 49 (2nd gen) beside Flow, through DirectLink

DirectLink is the Axiom's host mode: the script sends the handshake (`F0 00 01 05 20 7F 20 2E F7`) on `refresh_state` and leaves it (`... 20 00 F7`) on disconnect, and from then on the Axiom's controls send fixed messages on its DirectLink port, channel 16, whatever preset is loaded; the keys stay on "Axiom USB In". So Live's DirectLink input is Track off and nothing needs claiming - Flow reads that port over its own CoreMIDI connection. Always: faders F1-F8 (CC 33-40) track 1-8 volume, F9 (CC 41) master, Loop Rew FF Stop Play Rec (CC 113-118) the transport, Track < > (CC 110/111) select tracks. Encoders (CC 17-24) and pads (notes 60-72) are Flow's and not mapped. Inst (CC 109) flips Flow mode / DAW mode: in DAW mode F10-F16 (CC 49-55) arm tracks 1-7 and select them - with Shift (CC 13) held, arm only (F17/F18 step Flow's set row, Flow's side); in Flow mode the fader buttons are Flow's sets. The mode goes to `/Users/Shared/Flow/Bridge/axiom-mode` ("flow"/"daw") for Flow, and the LCD (five characters, `F0 00 01 05 20 7F 11 01 00 00 <text> F7`) says "DAW" / "FLOW" on a mode change. The number beside the text is not addressable; it shows the value a host last echoed on one of the Axiom's CCs. So a fader names its track ("3 Bas") and echoes its own value; an arm button (DAW mode) names its track and echoes the track's level 0-127 on its fader's CC (press and release). Everything else on the screen is Flow's (the bank at rest, a turned knob's name and value, a new set's name); the script's text stays up until Flow has news of its own. Live: a control-surface row of its own, input and output the Axiom's DirectLink ports, Track off on that input; no controller id, and Live's own Axiom_DirectLink must not be on the Axiom. Linked into Live's MIDI Remote Scripts like `cubefish`. Syntax-checked only: the decompiled `_Framework` here does not import under Python 3.13, and it has not yet been loaded in Live.

## `Launchkey_MK4_Flow/` — the flow toggle also hands over the Plugin layout's encoders

Shift + scene launch now also switches the encoders' Plugin layout between Ableton's device control ("live") and "flow": a `Flow_Encoders` component holds the eight encoders so nothing in Live moves, and `FlowEncoderTouchComponent` keeps the script from writing its knob readouts (it writes them on release, and would put "-" over Flow's). Going back to "live", each encoder display's send cache is cleared so Live's readouts are sent in full again. The owner goes to `/Users/Shared/Flow/Bridge/launchkey-encoders` ("flow"/"live"; "live" on disconnect) for Flow, which then reads the encoders off the DAW port and names them on their own displays. Syntax-checked; not yet loaded in Live.
