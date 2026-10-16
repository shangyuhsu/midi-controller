"""Launchkey Flow - keeps the Launchkey MK4 61's Custom Mode 1 out of Live's tracks.

Custom 1 is Flow's: Flow reads its pads and encoders over a CoreMIDI
connection of its own and lights the pads. But Custom Modes can only send on
the Launchkey's keys port, which Live has to listen to for the keys - so
without this every track listening to that port played and recorded the
pads. This script claims them: a message forwarded to a script never reaches
a track. It does nothing with them.

Ableton's own Launchkey MK4 script stays as it is, on its own row and the
DAW ports. This one goes on another row, input the Launchkey's keys port
("Launchkey MK4 61 (MIDI)"), output None. The keys are on channel 1 and
untouched.

Custom 1, as set up in Components - all on channel 15:
    pads      notes 36-51 (bottom row 36-43, top row 44-51)
    encoders  CC 21-28, relative
"""
from __future__ import absolute_import, print_function, unicode_literals
import Live
from _Framework.ButtonElement import ButtonElement
from _Framework.ControlSurface import ControlSurface
from _Framework.EncoderElement import EncoderElement
from _Framework.InputControlElement import MIDI_CC_TYPE, MIDI_NOTE_TYPE

CHANNEL = 14            # 0-based: MIDI channel 15
PAD_NOTES = range(36, 52)
ENCODER_CCS = range(21, 29)


class Launchkey_Flow(ControlSurface):

    def __init__(self, *a, **k):
        super(Launchkey_Flow, self).__init__(*a, **k)
        self._claimed = []

        with self.component_guard():
            for note in PAD_NOTES:
                self._claimed.append(ButtonElement(True, MIDI_NOTE_TYPE, CHANNEL, note, name="Pad_%d" % note))

            for cc in ENCODER_CCS:
                self._claimed.append(EncoderElement(MIDI_CC_TYPE, CHANNEL, cc, Live.MidiMap.MapMode.relative_binary_offset,
                                                    name="Encoder_%d" % cc))

            # A listener of the script's own is what makes Live forward the
            # message here - and a forwarded message is not passed to tracks.
            for control in self._claimed:
                control.add_value_listener(self._swallow)

        self.log_message("Launchkey_Flow: claiming %d pads and %d encoders on channel %d"
                         % (len(PAD_NOTES), len(ENCODER_CCS), CHANNEL + 1))

    def _swallow(self, value):
        pass

    def disconnect(self):
        for control in self._claimed:
            if control.value_has_listener(self._swallow):
                control.remove_value_listener(self._swallow)
        super(Launchkey_Flow, self).disconnect()
