from __future__ import absolute_import, print_function, unicode_literals
from functools import partial

import Live
from ableton.v2.base import clamp, listens, liveobj_valid
from ableton.v3.control_surface import Component

from .encoder import (
    CLIP_SYSEX_SLOT_OFFSET,
    KNOB_SYSEX_SYNC_TAG,
    SYSEX_END,
    SYSEX_NO_POSITION_SYNC,
    SYSEX_START,
)
from .util import _LOG

# Matches Live's internal WarpMode enum — see pushbase/clip_control_component.py
WARP_MODE_NAMES = {
    Live.Clip.WarpMode.beats:       "Beats",
    Live.Clip.WarpMode.tones:       "Tones",
    Live.Clip.WarpMode.texture:     "Texture",
    Live.Clip.WarpMode.repitch:     "Repitch",
    Live.Clip.WarpMode.complex:     "Complex",
    Live.Clip.WarpMode.complex_pro: "Pro",
}

# Encoder slot → (label, audio-clip-only?)
_PARAM_LABELS = [
    ("Transpose", True),
    ("Fine",      True),
    ("Gain",      True),
    ("Warp",      True),
    ("Warp Mode", True),
]


def _semitones_to_midi(v):
    return int(clamp((v + 48) * 127.0 / 96.0, 0, 127))


def _cents_to_midi(v):
    return int(clamp((v + 50.0) * 127.0 / 100.0, 0, 127))


class ClipModeComponent(Component):
    """
    Always-on component that keeps the firmware's clip display buffers
    (SysEx slots 33-48) fed with the currently focused clip's parameters.

    The firmware decides when to show clip mode — this component never
    receives a mode signal from Live. Hardware CC 60-75 → clip properties;
    clip property changes → SysEx feedback to firmware.

    Uses song.view.detail_clip (the clip open in Live's detail view),
    following the same pattern as Push's ClipControlComponent.
    """

    def __init__(self, send_midi, encoders, *a, **k):
        super().__init__(*a, **k)
        self._send_midi_fn = send_midi
        self._encoders = encoders
        self._clip = None
        self._last_sent = [None] * len(encoders)

        for idx, enc in enumerate(encoders):
            enc.add_value_listener(partial(self._on_encoder_value, idx))

        # Watch the detail clip (the clip shown in Live's clip/detail view)
        self._on_detail_clip_changed.subject = self.song.view
        self._on_detail_clip_changed()

    # ------------------------------------------------------------------ #
    # Clip selection                                                        #
    # ------------------------------------------------------------------ #

    @listens("detail_clip")
    def _on_detail_clip_changed(self):
        clip = self.song.view.detail_clip
        clip = clip if liveobj_valid(clip) else None
        self._clip = clip

        # Re-attach per-property listeners (all guarded: subject=None is safe)
        self._on_pitch_coarse_changed.subject = clip
        self._on_pitch_fine_changed.subject   = clip
        self._on_gain_changed.subject         = clip
        self._on_warping_changed.subject      = clip
        self._on_warp_mode_changed.subject    = clip

        self._last_sent = [None] * len(self._encoders)
        self._send_all_feedback()

    # ------------------------------------------------------------------ #
    # Per-property listeners — fire SysEx when Live changes the value     #
    # ------------------------------------------------------------------ #

    @listens("pitch_coarse")
    def _on_pitch_coarse_changed(self):
        self._send_feedback(0)

    @listens("pitch_fine")
    def _on_pitch_fine_changed(self):
        self._send_feedback(1)

    @listens("gain")
    def _on_gain_changed(self):
        self._send_feedback(2)

    @listens("warping")
    def _on_warping_changed(self):
        # Both "Warp on/off" and "Warp Mode" displays depend on warping state
        self._send_feedback(3)
        self._send_feedback(4)

    @listens("warp_mode")
    def _on_warp_mode_changed(self):
        self._send_feedback(4)

    # ------------------------------------------------------------------ #
    # Encoder → clip property                                              #
    # ------------------------------------------------------------------ #

    def _on_encoder_value(self, idx, value):
        clip = self._clip
        if not liveobj_valid(clip) or not clip.is_audio_clip:
            return
        try:
            if idx == 0:
                # Transpose: 0→-48st, 64→0st, 127→+48st
                clip.pitch_coarse = int(round(value * 96.0 / 127.0 - 48))
            elif idx == 1:
                # Fine: 0→-50ct, 64→0ct, 127→+50ct
                clip.pitch_fine = value * 100.0 / 127.0 - 50.0
            elif idx == 2:
                # Gain: 0.0–1.0 linear (matches Live's internal scale)
                clip.gain = clamp(value / 127.0, 0.0, 1.0)
            elif idx == 3:
                # Warp on/off toggle at mid-point
                clip.warping = value >= 64
            elif idx == 4:
                # Warp mode: step through clip.available_warp_modes
                modes = list(clip.available_warp_modes)
                if modes:
                    mode_idx = min(len(modes) - 1, int(value * len(modes) / 128))
                    clip.warp_mode = modes[mode_idx]
        except Exception as exc:
            _LOG(f"[ClipMode] enc{idx} set err: {exc}")

    # ------------------------------------------------------------------ #
    # SysEx feedback → firmware clip display buffers                       #
    # ------------------------------------------------------------------ #

    def _send_all_feedback(self):
        for idx in range(len(self._encoders)):
            self._send_feedback(idx)

    def _send_feedback(self, idx):
        enc        = self._encoders[idx]
        sysex_slot = enc.encoder_num + CLIP_SYSEX_SLOT_OFFSET
        clip       = self._clip

        name, value_str, midi_sync = self._build_display(idx, clip)

        display = f"{name}\n{value_str}".strip("\n")
        msg = (
            SYSEX_START, sysex_slot, KNOB_SYSEX_SYNC_TAG, midi_sync,
        ) + tuple(ord(c) for c in display) + (SYSEX_END,)

        if msg != self._last_sent[idx]:
            self._send_midi_fn(msg)
            self._last_sent[idx] = msg

    def _build_display(self, idx, clip):
        """Return (name, value_str, midi_sync) for the given slot."""
        if idx < len(_PARAM_LABELS):
            label, audio_only = _PARAM_LABELS[idx]
        else:
            return ("", "", SYSEX_NO_POSITION_SYNC)

        if not liveobj_valid(clip) or (audio_only and not clip.is_audio_clip):
            return (label, "---", SYSEX_NO_POSITION_SYNC)

        try:
            if idx == 0:
                v = int(clip.pitch_coarse)
                return ("Transpose", f"{v:+d} st", _semitones_to_midi(v))
            if idx == 1:
                v = clip.pitch_fine
                return ("Fine", f"{int(v):+d} ct", _cents_to_midi(v))
            if idx == 2:
                # gain_display_string gives the dB-formatted string Live uses
                midi = int(clamp(clip.gain * 127.0, 0, 127))
                return ("Gain", clip.gain_display_string, midi)
            if idx == 3:
                w = clip.warping
                return ("Warp", "On" if w else "Off", 127 if w else 0)
            if idx == 4:
                if clip.warping:
                    mode_name = WARP_MODE_NAMES.get(clip.warp_mode, "?")
                    modes = list(clip.available_warp_modes)
                    if modes and clip.warp_mode in modes:
                        mode_idx = modes.index(clip.warp_mode)
                        midi = int(mode_idx * 127 // max(len(modes) - 1, 1))
                    else:
                        midi = 0
                    return ("Warp Mode", mode_name, midi)
                return ("Warp Mode", "Off", 0)
        except Exception as exc:
            _LOG(f"[ClipMode] display idx={idx} err: {exc}")
            return (label, "err", SYSEX_NO_POSITION_SYNC)

        return (label, "---", SYSEX_NO_POSITION_SYNC)
