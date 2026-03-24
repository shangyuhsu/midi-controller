# Custom device bank layouts for cubefish (16 encoders, 8 bank keys).
# Merges with Live defaults so unlisted devices keep stock behavior.
#
# Eq8 / EQ Eight: stock Live banks are spread across many pages; this groups
# bands for faster access on the controller OLED labels.

from __future__ import absolute_import, print_function, unicode_literals

from ableton.v2.base.collection import IndexedDict
from ableton.v3.control_surface import BANK_PARAMETERS_KEY
from ableton.v3.control_surface.default_bank_definitions import BANK_DEFINITIONS

# --- Device class_name -> bank layout (same format as Live defaults) -----------

_CUBEFISH_EQ8 = IndexedDict(
    (
        (
            "1-4 Freq / Gain",
            {
                BANK_PARAMETERS_KEY: (
                    "1 Frequency A",
                    "1 Gain A",
                    "2 Frequency A",
                    "2 Gain A",
                    "3 Frequency A",
                    "3 Gain A",
                    "4 Frequency A",
                    "4 Gain A",
                )
            },
        ),
        (
            "5-8 Freq / Gain",
            {
                BANK_PARAMETERS_KEY: (
                    "5 Frequency A",
                    "5 Gain A",
                    "6 Frequency A",
                    "6 Gain A",
                    "7 Frequency A",
                    "7 Gain A",
                    "8 Frequency A",
                    "8 Gain A",
                )
            },
        ),
        (
            "1-4 Res / Type",
            {
                BANK_PARAMETERS_KEY: (
                    "1 Resonance A",
                    "1 Filter Type A",
                    "2 Resonance A",
                    "2 Filter Type A",
                    "3 Resonance A",
                    "3 Filter Type A",
                    "4 Resonance A",
                    "4 Filter Type A",
                )
            },
        ),
        (
            "5-8 Res / Type",
            {
                BANK_PARAMETERS_KEY: (
                    "5 Resonance A",
                    "5 Filter Type A",
                    "6 Resonance A",
                    "6 Filter Type A",
                    "7 Resonance A",
                    "7 Filter Type A",
                    "8 Resonance A",
                    "8 Filter Type A",
                )
            },
        ),
        (
            "Band On/Off",
            {
                BANK_PARAMETERS_KEY: (
                    "1 Filter On A",
                    "2 Filter On A",
                    "3 Filter On A",
                    "4 Filter On A",
                    "5 Filter On A",
                    "6 Filter On A",
                    "7 Filter On A",
                    "8 Filter On A",
                )
            },
        ),
        (
            "All Frequencies",
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
            "All Gains",
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
