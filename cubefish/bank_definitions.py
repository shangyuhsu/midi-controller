# Custom device bank layouts for cubefish (16 encoders, 8 bank keys).
# Merges with Live defaults so unlisted devices keep stock behavior.
#
# Eq8 / EQ Eight: banks 1–4 = two bands each (freq, gain, res, on/off per band).
# Banks 5–8 = filter types, all freqs, all gains, output.

from __future__ import absolute_import, print_function, unicode_literals

from ableton.v2.base.collection import IndexedDict
from ableton.v3.control_surface import BANK_PARAMETERS_KEY
from ableton.v3.control_surface.default_bank_definitions import BANK_DEFINITIONS


def _eq8_pair_bank(lo, hi, title):
    """One bank: band lo then band hi, each Freq, Gain, Res, Filter On (8 encoders)."""
    return (
        title,
        {
            BANK_PARAMETERS_KEY: (
                "%d Frequency A" % lo,
                "%d Gain A" % lo,
                "%d Resonance A" % lo,
                "%d Filter On A" % lo,
                "%d Frequency A" % hi,
                "%d Gain A" % hi,
                "%d Resonance A" % hi,
                "%d Filter On A" % hi,
            )
        },
    )


# --- Device class_name -> bank layout (same format as Live defaults) -----------

_CUBEFISH_EQ8 = IndexedDict(
    (
        _eq8_pair_bank(1, 2, "Banks 1-2"),
        _eq8_pair_bank(3, 4, "Banks 3-4"),
        _eq8_pair_bank(5, 6, "Banks 5-6"),
        _eq8_pair_bank(7, 8, "Banks 7-8"),
        (
            "Filter types",
            {
                BANK_PARAMETERS_KEY: (
                    "1 Filter Type A",
                    "2 Filter Type A",
                    "3 Filter Type A",
                    "4 Filter Type A",
                    "5 Filter Type A",
                    "6 Filter Type A",
                    "7 Filter Type A",
                    "8 Filter Type A",
                )
            },
        ),
        (
            "All frequency",
            {
                BANK_PARAMETERS_KEY: (
                    "1 Frequency A",
                    "2 Frequency A",
                    "3 Frequency A",
                    "4 Frequency A",
                    "5 Frequency A",
                    "6 Frequency A",
                    "7 Frequency A",
                    "8 Frequency A",
                )
            },
        ),
        (
            "All gain",
            {
                BANK_PARAMETERS_KEY: (
                    "1 Gain A",
                    "2 Gain A",
                    "3 Gain A",
                    "4 Gain A",
                    "5 Gain A",
                    "6 Gain A",
                    "7 Gain A",
                    "8 Gain A",
                )
            },
        ),
        (
            "Output",
            {
                BANK_PARAMETERS_KEY: (
                    "Adaptive Q",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "Scale",
                    "Output Gain",
                )
            },
        ),
    )
)

# EQ Three — short names for small OLED; same parameters as stock FilterEQ3.
_CUBEFISH_FILTEREQ3 = IndexedDict(
    (
        (
            "EQ",
            {
                BANK_PARAMETERS_KEY: (
                    "LowOn",
                    "MidOn",
                    "HighOn",
                    "GainLo",
                    "GainMid",
                    "GainHi",
                    "FreqLo",
                    "FreqHi",
                )
            },
        ),
        ("Slope", {BANK_PARAMETERS_KEY: ("Slope", "", "", "", "", "", "", "")}),
    )
)


def build_cubefish_bank_definitions():
    """Shallow copy of Live defaults plus cubefish overrides."""
    merged = dict(BANK_DEFINITIONS)
    merged["Eq8"] = _CUBEFISH_EQ8
    merged["FilterEQ3"] = _CUBEFISH_FILTEREQ3
    return merged


CUBEFISH_BANK_DEFINITIONS = build_cubefish_bank_definitions()
