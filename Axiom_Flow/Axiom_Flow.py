"""Axiom Flow - the M-Audio Axiom 49 (2nd gen) in Live, beside Flow.

The Axiom has one port for everything ("Axiom USB In"), and Live has to
listen to it for the keys - so without this every track listening to it
played and recorded Flow's knobs and pads. This script claims those (a
message forwarded to a script never reaches a track) and does nothing with
them: Flow reads them over a CoreMIDI connection of its own.

Two presets on the Axiom, told apart by channel:

    Flow (patch 1)  encoders E1-E8   CC 38-45 ch 1, Rel. Bin Offset
                    pads P1-P8       notes 61 60 64 63 81 80 76 62, ch 10
                    buttons F10-F18  CC 24-32 ch 1
                    faders F1-F9     ch 1, left to the tracks
    DAW (patch 2)   the same, but faders F1-F9 and buttons F10-F18 on ch 2:
                    F1-F8   track 1-8 volume (CC 73 75 72 74 79 84 89 90)
                    F9      master volume (CC 7)
                    F10-F16 track 1-7 arm (CC 24-30)
                    F17/F18 Flow's set left / right (CC 31/32) - claimed

The fader buttons are toggles (127, then 0 on the next press), so the arm
buttons are not momentary: either value is one press, which toggles.

Live: a Control Surface row of its own, input the Axiom's "Axiom USB In"
port, output None. No controller id, so Live never picks it by itself - and
Live's own Axiom_DirectLink script must not be on the Axiom either.
"""
from __future__ import absolute_import, print_function, unicode_literals
import Live
from _Framework.ButtonElement import ButtonElement
from _Framework.ButtonMatrixElement import ButtonMatrixElement
from _Framework.ControlSurface import ControlSurface
from _Framework.EncoderElement import EncoderElement
from _Framework.InputControlElement import MIDI_CC_TYPE, MIDI_NOTE_TYPE
from _Framework.Layer import Layer
from _Framework.MixerComponent import MixerComponent
from _Framework.SliderElement import SliderElement

# 0-based channels.
FLOW_CHANNEL = 0
PAD_CHANNEL = 9
DAW_CHANNEL = 1

ENCODER_CCS = range(38, 46)
PAD_NOTES = (61, 60, 64, 63, 81, 80, 76, 62)
FLOW_BUTTON_CCS = range(24, 33)

TRACK_FADER_CCS = (73, 75, 72, 74, 79, 84, 89, 90)
MASTER_FADER_CC = 7
ARM_BUTTON_CCS = range(24, 31)
SET_STEP_CCS = (31, 32)


class Axiom_Flow(ControlSurface):

    def __init__(self, *a, **k):
        super(Axiom_Flow, self).__init__(*a, **k)
        self._claimed = []

        with self.component_guard():
            self._create_flow_controls()
            self._create_mixer()

        self.log_message("Axiom_Flow: claiming %d Flow controls; F1-F9 / F10-F16 on ch %d drive the mixer"
                         % (len(self._claimed), DAW_CHANNEL + 1))

    def _create_flow_controls(self):
        for cc in ENCODER_CCS:
            self._claimed.append(EncoderElement(MIDI_CC_TYPE, FLOW_CHANNEL, cc,
                                                Live.MidiMap.MapMode.relative_binary_offset,
                                                name="Encoder_%d" % (cc - ENCODER_CCS[0] + 1)))

        for n, note in enumerate(PAD_NOTES):
            self._claimed.append(ButtonElement(True, MIDI_NOTE_TYPE, PAD_CHANNEL, note, name="Pad_%d" % (n + 1)))

        for cc in FLOW_BUTTON_CCS:
            self._claimed.append(ButtonElement(False, MIDI_CC_TYPE, FLOW_CHANNEL, cc, name="Flow_Button_%d" % cc))

        for cc in SET_STEP_CCS:
            self._claimed.append(ButtonElement(False, MIDI_CC_TYPE, DAW_CHANNEL, cc, name="Set_Step_%d" % cc))

        # A listener of the script's own is what makes Live forward the
        # message here - and a forwarded message is not passed to tracks.
        for control in self._claimed:
            control.add_value_listener(self._swallow)

    def _create_mixer(self):
        faders = [SliderElement(MIDI_CC_TYPE, DAW_CHANNEL, cc, name="Volume_%d" % (n + 1))
                  for n, cc in enumerate(TRACK_FADER_CCS)]
        arms = [ButtonElement(False, MIDI_CC_TYPE, DAW_CHANNEL, cc, name="Arm_%d" % (n + 1))
                for n, cc in enumerate(ARM_BUTTON_CCS)]

        mixer = MixerComponent(len(faders), name="Mixer", is_enabled=False,
                               layer=Layer(volume_controls=ButtonMatrixElement(rows=[faders]),
                                           arm_buttons=ButtonMatrixElement(rows=[arms])))
        mixer.master_strip().set_volume_control(SliderElement(MIDI_CC_TYPE, DAW_CHANNEL, MASTER_FADER_CC,
                                                              name="Master_Volume"))
        mixer.set_enabled(True)

    def _swallow(self, value):
        pass

    def disconnect(self):
        for control in self._claimed:
            if control.value_has_listener(self._swallow):
                control.remove_value_listener(self._swallow)
        super(Axiom_Flow, self).disconnect()
