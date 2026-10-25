"""Axiom Flow - the M-Audio Axiom 49 (2nd gen) in Live, beside Flow, through DirectLink.

DirectLink is the Axiom's host mode: a handshake on its DirectLink port, and
from then on its controls send the firmware's own messages on that port,
channel 16, whatever preset is loaded - apart from the keys, which stay on
"Axiom USB In". So the DirectLink port can be Track off in Live: nothing on it
reaches a track, and nothing needs claiming. Flow reads the same port over a
CoreMIDI connection of its own.

Measured on the device (all ch 16, buttons momentary):
    encoders E1-E8   CC 17-24      Flow's knobs - not mapped here
    pads P1-P8       notes 60-72   Flow's banks - not mapped here
    faders F1-F8     CC 33-40      track 1-8 volume
    fader F9         CC 41         master volume
    buttons F10-F18  CC 49-57      Flow mode: Flow's sets (F17 its pad mode)
                                   DAW mode: F10-F16 arm tracks 1-7,
                                   F17 / F18 step Flow's set row
    Loop Rew FF Stop Play Rec  CC 113-118
    Inst             CC 109        Flow mode <-> DAW mode
    Track < / >      CC 110 / 111  select the previous / next track

The mode is this script's: Inst flips it, and it is written to
/Users/Shared/Flow/Bridge/axiom-mode ("flow" or "daw") for Flow, which reads it
ten times a second - a remote script cannot reach a plugin. The LCD shows "DAW"
on entering DAW mode; in Flow mode Flow writes the set's name there.

Live: a Control Surface row of its own, input and output the Axiom's
"DirectLink" ports, with Track off for the DirectLink input. Its keys port
("Axiom USB In") stays a plain track input. Live's own Axiom_DirectLink must not
be on the Axiom.
"""
from __future__ import absolute_import, print_function, unicode_literals
import os
from _Framework.ButtonElement import ButtonElement
from _Framework.ButtonMatrixElement import ButtonMatrixElement
from _Framework.ControlSurface import ControlSurface
from _Framework.InputControlElement import MIDI_CC_TYPE
from _Framework.Layer import Layer
from _Framework.MixerComponent import MixerComponent
from _Framework.SliderElement import SliderElement
from _Framework.TransportComponent import TransportComponent

CHANNEL = 15                # 0-based: MIDI channel 16
SYSEX_START = (240, 0, 1, 5, 32, 127)
DIRECTLINK_ON = SYSEX_START + (32, 46, 247)
DIRECTLINK_OFF = SYSEX_START + (32, 0, 247)
DISPLAY_START = SYSEX_START + (17, 1, 0, 0)

TRACK_FADER_CCS = range(33, 41)
MASTER_FADER_CC = 41
ARM_BUTTON_CCS = range(49, 56)
INST_CC = 109
PREV_TRACK_CC, NEXT_TRACK_CC = 110, 111
LOOP_CC, REWIND_CC, FORWARD_CC, STOP_CC, PLAY_CC, RECORD_CC = 113, 114, 115, 116, 117, 118

MODE_FILE = "/Users/Shared/Flow/Bridge/axiom-mode"


def _button(cc, name):
    return ButtonElement(True, MIDI_CC_TYPE, CHANNEL, cc, name=name)


class Axiom_Flow(ControlSurface):

    def __init__(self, *a, **k):
        super(Axiom_Flow, self).__init__(*a, **k)
        self._daw_mode = False

        with self.component_guard():
            self._create_transport()
            self._create_mixer()
            self._inst_button = _button(INST_CC, "Inst_Button")
            self._inst_button.add_value_listener(self._inst_value)

        self._write_mode()
        self.log_message("Axiom_Flow: DirectLink on channel %d, Flow mode" % (CHANNEL + 1))

    def _create_transport(self):
        transport = TransportComponent(name="Transport", is_enabled=False,
                                       layer=Layer(play_button=_button(PLAY_CC, "Play_Button"),
                                                   stop_button=_button(STOP_CC, "Stop_Button"),
                                                   record_button=_button(RECORD_CC, "Record_Button"),
                                                   loop_button=_button(LOOP_CC, "Loop_Button"),
                                                   seek_forward_button=_button(FORWARD_CC, "Forward_Button"),
                                                   seek_backward_button=_button(REWIND_CC, "Rewind_Button")))
        transport.set_enabled(True)

    def _create_mixer(self):
        faders = [SliderElement(MIDI_CC_TYPE, CHANNEL, cc, name="Volume_%d" % (n + 1))
                  for n, cc in enumerate(TRACK_FADER_CCS)]
        self._arm_buttons = ButtonMatrixElement(rows=[[_button(cc, "Arm_%d" % (n + 1))
                                                       for n, cc in enumerate(ARM_BUTTON_CCS)]])

        self._mixer = MixerComponent(len(faders), name="Mixer", is_enabled=False,
                                     layer=Layer(volume_controls=ButtonMatrixElement(rows=[faders])))
        self._mixer.master_strip().set_volume_control(SliderElement(MIDI_CC_TYPE, CHANNEL, MASTER_FADER_CC,
                                                                    name="Master_Volume"))
        self._mixer.set_select_buttons(_button(NEXT_TRACK_CC, "Next_Track_Button"),
                                       _button(PREV_TRACK_CC, "Prev_Track_Button"))
        self._mixer.set_enabled(True)

    def _inst_value(self, value):
        if value == 0:
            return

        self._daw_mode = not self._daw_mode

        # Flow mode: the fader buttons are Flow's sets, so nothing of Live's on them.
        self._mixer.set_arm_buttons(self._arm_buttons if self._daw_mode else None)
        self._write_mode()

        if self._daw_mode:
            self._show("DAW")

        self.log_message("Axiom_Flow: %s mode" % ("DAW" if self._daw_mode else "Flow"))

    def _write_mode(self):
        try:
            if not os.path.isdir(os.path.dirname(MODE_FILE)):
                os.makedirs(os.path.dirname(MODE_FILE))
            with open(MODE_FILE, "w") as f:
                f.write(("daw" if self._daw_mode else "flow") + "\n")
        except Exception as e:
            self.log_message("Axiom_Flow: could not write %s: %s" % (MODE_FILE, e))

    def _show(self, text):
        text = (text + "     ")[:5]
        self._send_midi(DISPLAY_START + tuple(ord(c) if 32 <= ord(c) < 127 else 63 for c in text) + (247,))

    def refresh_state(self):
        # DirectLink is entered by asking; the Axiom answers in the same form.
        super(Axiom_Flow, self).refresh_state()
        self.schedule_message(3, self._send_midi, DIRECTLINK_ON)

    def handle_sysex(self, midi_bytes):
        if midi_bytes[:len(SYSEX_START) + 1] == SYSEX_START + (32,):
            self.log_message("Axiom_Flow: the Axiom is in DirectLink mode")
            self._show("DAW" if self._daw_mode else "FLOW")
        else:
            super(Axiom_Flow, self).handle_sysex(midi_bytes)

    def disconnect(self):
        self._inst_button.remove_value_listener(self._inst_value)
        self._daw_mode = False
        self._write_mode()
        self._show("     ")
        self._send_midi(DIRECTLINK_OFF)
        super(Axiom_Flow, self).disconnect()
