from __future__ import absolute_import, print_function, unicode_literals
from ableton.v3.control_surface.elements import EncoderElement as EncoderElementBase
from ableton.v3.live import liveobj_valid, parameter_value_to_midi_value
from .util import _LOG
SYSEX_START = 0xF0
SYSEX_END = 0xF7
# Must match live_controller.ino
KNOB_SYSEX_SYNC_TAG = 0x01   # Has parameter: F0, slot, 0x01, midi, display..., F7
KNOB_SYSEX_CLEAR_TAG = 0x02  # No parameter:  F0, slot, 0x02, F7
# Second SysEx data byte offsets — must match const.h ranges
MIXER_SYSEX_SLOT_OFFSET = 16  # slots 17–32
CLIP_SYSEX_SLOT_OFFSET  = 32  # slots 33–48

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

        # Firmware protocol:
        #   With sync: F0, slot, SYNC_TAG(0x01), midi_value(0-127), display..., F7
        #   Clear:     F0, slot, CLEAR_TAG(0x02), F7
        if liveobj_valid(self.mapped_object):
            midi_sync = parameter_value_to_midi_value(
                self.mapped_object, max_value=(self._max_value))
            midi_msg = (
                SYSEX_START,
                self.encoder_num,
                KNOB_SYSEX_SYNC_TAG,
                midi_sync,
            ) + tuple(ord(char) for char in val) + (SYSEX_END,)
        else:
            midi_msg = (
                SYSEX_START,
                self.encoder_num,
                KNOB_SYSEX_CLEAR_TAG,
                SYSEX_END,
            )
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
            _LOG(f"[ENC] sysex enc={self.encoder_num} msg={message}")
            self.send_midi(message)
        self._last_sent_parameter_message = message

    def release_parameter(self):
        super().release_parameter()
        _LOG(f"[ENC] release enc={self.encoder_num}")
        # The base class defers notify_parameter_name via a task, which can race
        # against the next display update. Clear the OLED immediately instead.
        # Force-clear cache so the empty message is always sent.
        self._last_sent_parameter_message = None
        self._send_parameter_feedback()



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
        sysex_slot = self.encoder_num + MIXER_SYSEX_SLOT_OFFSET
        if liveobj_valid(self.mapped_object):
            midi_sync = parameter_value_to_midi_value(
                self.mapped_object, max_value=(self._max_value))
            midi_msg = (
                SYSEX_START,
                sysex_slot,
                KNOB_SYSEX_SYNC_TAG,
                midi_sync,
            ) + tuple(ord(char) for char in val) + (SYSEX_END,)
        else:
            midi_msg = (
                SYSEX_START,
                sysex_slot,
                KNOB_SYSEX_CLEAR_TAG,
                SYSEX_END,
            )
        self._send_message(midi_msg)


class ClipEncoderElement(EncoderElementBase):
    """Plain CC input element for clip mode. encoder_num (1-16) is used by
    ClipModeComponent to compute the SysEx slot (encoder_num + CLIP_SYSEX_SLOT_OFFSET)."""

    def __init__(self, encoder_num, *a, **k):
        (super().__init__)(*a, **k)
        self.encoder_num = encoder_num


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