"""MPK249 Flow - the factory MPK249 script, plus Port A's pads and knobs as
named controls for the "MPK249 Control" Max for Live device.

Select it in Live's Preferences > Link/Tempo/MIDI as a Control Surface with
"MPK249 (Port A)" as its input and output.

What it does itself is only what the factory script did - transport, the
faders on the first eight tracks' volumes, the switches arming them - less the
Loop button. That, and Port A's 16 pads and 8 knobs, it only claims: every message from them is forwarded to
the script, so Live never passes it on to a track - no stray notes in a
plugin, none recorded into a clip. What they DO lives in the Max device
(mpk249_control/), which grabs them by name and observes their values, so it
can be changed without restarting Live.

Pads are Akai's numbering: pad 1 bottom left, pad 13 top left.
"""
from __future__ import absolute_import, print_function, unicode_literals
import Live
from _Framework.ButtonElement import ButtonElement
from _Framework.ControlSurface import ControlSurface
from _Framework.EncoderElement import EncoderElement
from _Framework.InputControlElement import MIDI_CC_TYPE, MIDI_NOTE_TYPE
from _Framework.Layer import Layer
from _Framework.MidiMap import MidiMap as MidiMapBase
from _Framework.MidiMap import make_button, make_slider
from _Framework.MixerComponent import MixerComponent
from _Framework.TransportComponent import TransportComponent

# Port A's pad bank A, as set in the MPK's preset: USB A1, pad 1 = C1 (36) ...
# pad 13 = C3 (48), pad 16 = D#3 (51) in Akai's octave naming.
PAD_CHANNEL = 0
PAD_FIRST_NOTE = 36
NUM_PADS = 16

# Port A's knob bank A: USB A1, CC 22-29, Inc/Dec 2 (two's complement).
ENCODER_CHANNEL = 0
ENCODER_FIRST_CC = 22
NUM_ENCODERS = 8


class MidiMap(MidiMapBase):
    """The factory script's map, less its pan encoders (the knobs are the
    device's now) and its drum pads (on channel 2, which the preset no longer
    sends)."""

    def __init__(self, *a, **k):
        super(MidiMap, self).__init__(*a, **k)
        self.add_button("Play", 0, 118, MIDI_CC_TYPE)
        self.add_button("Record", 0, 119, MIDI_CC_TYPE)
        self.add_button("Stop", 0, 117, MIDI_CC_TYPE)
        self.add_button("Loop", 0, 114, MIDI_CC_TYPE)
        self.add_button("Forward", 0, 116, MIDI_CC_TYPE)
        self.add_button("Backward", 0, 115, MIDI_CC_TYPE)
        self.add_matrix("Sliders", make_slider, 0, [[12, 13, 14, 15, 16, 17, 18, 19]], MIDI_CC_TYPE)
        self.add_matrix("Arm_Buttons", make_button, 0, [[32, 33, 34, 35, 36, 37, 38, 39]], MIDI_CC_TYPE)


class MPK249_Flow(ControlSurface):

    def __init__(self, *a, **k):
        super(MPK249_Flow, self).__init__(*a, **k)
        with self.component_guard():
            self._create_factory_controls()
            self._create_device_controls()
        self.log_message("MPK249_Flow: %d pads (notes %d-%d, ch %d), %d knobs (CC %d-%d, ch %d)"
                         % (NUM_PADS, PAD_FIRST_NOTE, PAD_FIRST_NOTE + NUM_PADS - 1, PAD_CHANNEL + 1,
                            NUM_ENCODERS, ENCODER_FIRST_CC, ENCODER_FIRST_CC + NUM_ENCODERS - 1, ENCODER_CHANNEL + 1))

    def _create_factory_controls(self):
        midimap = MidiMap()

        # The Loop button is the device's (Cmd-L, loop the selection), claimed like the pads.
        self._loop_button = midimap["Loop"]
        transport = TransportComponent(name="Transport", is_enabled=False,
                                       layer=Layer(play_button=midimap["Play"],
                                                   record_button=midimap["Record"],
                                                   stop_button=midimap["Stop"],
                                                   seek_forward_button=midimap["Forward"],
                                                   seek_backward_button=midimap["Backward"]))
        transport.set_enabled(True)
        mixer = MixerComponent(len(midimap["Sliders"]), name="Mixer", is_enabled=False,
                               layer=Layer(volume_controls=midimap["Sliders"],
                                           arm_buttons=midimap["Arm_Buttons"]))
        mixer.set_enabled(True)

    def _create_device_controls(self):
        """Named so the Max device can find them: Pad_1..Pad_16, Encoder_1..Encoder_8.

        A listener of the script's own on each is what makes Live forward the
        message to the script - and a forwarded message is not passed on to
        tracks. Without one, with the Max device not loaded, a pad would play
        its note into whatever track is armed.
        """
        self._device_controls = []

        for n in range(1, NUM_PADS + 1):
            pad = ButtonElement(True, MIDI_NOTE_TYPE, PAD_CHANNEL, PAD_FIRST_NOTE + n - 1, name="Pad_%d" % n)
            self._device_controls.append(pad)

        for n in range(1, NUM_ENCODERS + 1):
            encoder = EncoderElement(MIDI_CC_TYPE, ENCODER_CHANNEL, ENCODER_FIRST_CC + n - 1,
                                     Live.MidiMap.MapMode.relative_two_compliment, name="Encoder_%d" % n)
            self._device_controls.append(encoder)

        self._device_controls.append(self._loop_button)

        for control in self._device_controls:
            control.add_value_listener(self._swallow)

    def _swallow(self, value):
        pass

    def disconnect(self):
        for control in self._device_controls:
            if control.value_has_listener(self._swallow):
                control.remove_value_listener(self._swallow)
        super(MPK249_Flow, self).disconnect()
