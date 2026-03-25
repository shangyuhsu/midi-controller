from __future__ import absolute_import, print_function, unicode_literals
from ableton.v3.control_surface.elements import EncoderElement as EncoderElementBase
from ableton.v3.live import liveobj_valid, parameter_value_to_midi_value
SYSEX_START = 0xF0
SYSEX_END = 0xF7
# Firmware uses 0-127 for position sync; 128 = skip sync (unmapped / no parameter)
SYSEX_NO_POSITION_SYNC = 128
# Must match live_controller.ino CUBEFISH_KNOB_SYNC_TAG
KNOB_SYSEX_SYNC_TAG = 0x01

CC_STATUS = 176


def _track_for_mixer_parameter(song, param):
    if not liveobj_valid(song) or not liveobj_valid(param):
        return None
    for track in song.tracks:
        if not liveobj_valid(track):
            continue
        md = track.mixer_device
        if not liveobj_valid(md):
            continue
        if md.volume == param or md.panning == param:
            return track
    return None


class CustomEncoderElement(EncoderElementBase):

    def __init__(self, encoder_num, *a, **k):
        (super().__init__)(*a, **k)
        self.encoder_num = encoder_num
        self._last_sent_parameter_message = None

    def notify_parameter_name(self):
        super().notify_parameter_name()
        self._send_parameter_feedback()

    def notify_parameter_value(self):
        super().notify_parameter_value()
        self._send_parameter_feedback()

    def clear_send_cache(self):
        super().clear_send_cache()
        self._last_sent_parameter_message = None

    def _send_parameter_feedback(self):
        # Send "Name: Value" for display (e.g. "Cutoff: 15kHz")
        name = self.parameter_name or ""
        value_str = self.parameter_value or ""
        if name.startswith("1 E"):
            name = name[name.find("\n") + 1:]
        elif name:
            if name.startswith("1 A "):
                name = name[4:]
            elif name.startswith("1 B "):
                name = name[4:]
            elif name.startswith("1 "):
                name = name[2:]
            if name.startswith("AmpEnv"):
                name = "Ae " + name[6:]
            elif name.startswith("FEnv"):
                name = "Fe " + name[4:]
        if value_str.startswith("1 A "):
            value_str = value_str[4:]
        elif value_str.startswith("1 B "):
            value_str = value_str[4:]
        elif value_str.startswith("1 "):
            value_str = value_str[2:]

        val = f"{name}\n{value_str}".strip("\n") if name or value_str else ""

        if liveobj_valid(self.mapped_object):
            midi_sync = parameter_value_to_midi_value(
                self.mapped_object, max_value=(self._max_value))
        else:
            midi_sync = SYSEX_NO_POSITION_SYNC
        # Firmware: F0, enc 1-16, KNOB_SYSEX_SYNC_TAG, midi 0-127 or 128=skip, display..., F7
        midi_msg = (
            SYSEX_START,
            self.encoder_num,
            KNOB_SYSEX_SYNC_TAG,
            midi_sync,
        ) + tuple(ord(char) for char in val) + (SYSEX_END,)
        self._send_message(midi_msg)

        # midi_msg = (0xB0 | self._msg_channel,) + (1, ident, self.)
        # _LOG(f"{midi_msg}")

        # self._send_message(midi_msg)
        # if liveobj_valid(self._mapped_object):
        #     self._send_message(make_parameter_message(ident, self.parameter_name, self.parameter_value))
        # else:
        #     self._send_message(make_blank_parameter_message(ident))

    def _send_message(self, message):
        if message != self._last_sent_parameter_message:
            self.send_midi(message)
        self._last_sent_parameter_message = message

    def _parameter_value_changed(self):
        super()._parameter_value_changed()
        # _LOG("PARAM VAL CHANGED")


class MixerStripEncoderElement(CustomEncoderElement):

    def __init__(self, encoder_num, song_getter, identifier, *a, **k):
        self._song_getter = song_getter
        (super().__init__)(encoder_num, identifier, *a, **k)

    def _send_parameter_feedback(self):
        song = self._song_getter() if self._song_getter else None
        param = self.mapped_object
        track = _track_for_mixer_parameter(song, param)
        name = ""
        if track is not None:
            name = (track.name or "")[:18]
        if not name:
            name = self.parameter_name or ""
        value_str = self.parameter_value or ""
        if value_str.startswith("1 A "):
            value_str = value_str[4:]
        elif value_str.startswith("1 B "):
            value_str = value_str[4:]
        elif value_str.startswith("1 "):
            value_str = value_str[2:]
        val = f"{name}\n{value_str}".strip("\n") if name or value_str else ""
        if liveobj_valid(self.mapped_object):
            midi_sync = parameter_value_to_midi_value(
                self.mapped_object, max_value=(self._max_value))
        else:
            midi_sync = SYSEX_NO_POSITION_SYNC
        midi_msg = (
            SYSEX_START,
            self.encoder_num,
            KNOB_SYSEX_SYNC_TAG,
            midi_sync,
        ) + tuple(ord(char) for char in val) + (SYSEX_END,)
        self._send_message(midi_msg)


# class RealigningEncoderElement(EncoderElement):

#     def __init__(self, *a, **k):
#         (super().__init__)(*a, **k)
#         self._sysex_header = ENCODER_VALUE_HEADER + (
#          ENCODER_ID_TO_SYSEX_ID[self.message_identifier()],
#          0)
#         self._last_mapped_value = None

#     def realign_value(self):
#         value_to_send = self._last_mapped_value or self._last_received_value or 0
#         self.send_midi(self._sysex_header + (value_to_send, SYSEX_END))

#     def receive_value(self, value):
#         super().receive_value(value)
#         self._last_mapped_value = None

#     def _parameter_value_changed(self):
#         if liveobj_valid(self._mapped_object):
#             self._last_mapped_value = parameter_value_to_midi_value(self._mapped_object)