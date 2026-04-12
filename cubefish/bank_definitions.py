# Custom device bank layouts for cubefish (16 encoders, 8 bank keys).
# Merges with Live defaults so unlisted devices keep stock behavior.
#
# Eq8 / EQ Eight: banks 1–4 = two bands each (freq, gain, res, on/off per band).
# Banks 5–8 = filter types, all freqs, all gains, output.

from __future__ import absolute_import, print_function, unicode_literals

from ableton.v2.base.collection import IndexedDict
from ableton.v3.control_surface import BANK_PARAMETERS_KEY, use
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
        (
            "Output",
            {
                BANK_PARAMETERS_KEY: (
                    "Output Gain",
                    "Adaptive Q",
                    "Scale",
                    "",
                    "",
                    "",
                    "",
                    "",
                )
            },
        ),
        (
            "+",
            {
                BANK_PARAMETERS_KEY: (
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                )
            },
        ),
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
    )
)

# Reverb — 4 banks of 8 parameters (framework combines pairs with bank_size=16)
_CUBEFISH_REVERB = IndexedDict(
    (
        (
            "Input",
            {
                BANK_PARAMETERS_KEY: (
                    "In LowCut On", "In HighCut On", "In Filter Freq", "In Filter Width",
                    "LowShelf On", "LowShelf Freq", "LowShelf Gain", "Scale",
                )
            },
        ),
        (
            "Core",
            {
                BANK_PARAMETERS_KEY: (
                    "HiFilter On", "HiFilter Freq", "HiShelf Gain", "Diffusion",
                    "Predelay", "Room Size", "Decay Time", "Dry/Wet",
                )
            },
        ),
        (
            "Global",
            {
                BANK_PARAMETERS_KEY: (
                    "Reflect Level", "Diffuse Level", "Stereo Image", "Density",
                    "Freeze On", "Flat On", "", "",
                )
            },
        ),
        (
            "ER/Chorus",
            {
                BANK_PARAMETERS_KEY: (
                    "ER Spin On", "ER Spin Rate", "ER Spin Amount", "ER Shape",
                    "Chorus On", "Chorus Rate", "Chorus Amount", "",
                )
            },
        ),
    )
)

# Delay — 4 banks of 8 parameters
_CUBEFISH_DELAY = IndexedDict(
    (
        (
            "Time",
            {
                BANK_PARAMETERS_KEY: (
                    # L timing: 16th when synced, Time when not
                    use("L 16th").if_parameter("L Sync").has_value("On").else_use("L Time"),
                    # R timing: follows R settings when unlinked, follows L when linked
                    use("R 16th").if_parameter("R Sync").has_value("On").and_parameter("Link").has_value("Off").else_use("R Time").if_parameter("Link").has_value("Off").else_use("L 16th").if_parameter("L Sync").has_value("On").else_use("L Time"),
                    # L/R sync mode selectors
                    use("L Sync Enum").with_name("L Mode"),
                    use("R Sync Enum").with_name("R Mode").if_parameter("Link").has_value("Off").else_use("L Sync Enum").with_name("(Linked)"),
                    "L Offset", "R Offset", "Feedback", "Dry/Wet",
                )
            },
        ),
        (
            "Filter/Mod",
            {
                BANK_PARAMETERS_KEY: (
                    "Link", "Filter On", "Filter Freq", "Filter Width",
                    use("Mod Freq").with_name("Mod Rate"), "Filter < Mod", "Dly < Mod", "Ping Pong",
                )
            },
        ),
        (
            "Misc",
            {
                BANK_PARAMETERS_KEY: (
                    use("Delay Mode").with_name("DlayMd"), "Freeze", "", "",
                    "", "", "", "",
                )
            },
        ),
    )
)

# EQ Three — organized into logical groups
_CUBEFISH_FILTEREQ3 = IndexedDict(
    (
        (
            "Main",
            {
                BANK_PARAMETERS_KEY: (
                    "GainLo", "GainMid", "GainHi", "", "FreqLo", "Slope", "FreqHi", "",
                )
            },
        ),
        (
            "On/Off",
            {
                BANK_PARAMETERS_KEY: (
                    "LowOn", "MidOn", "HighOn", "", "", "", "", "",
                )
            },
        ),
    )
)


def build_cubefish_bank_definitions():
    """Shallow copy of Live defaults plus cubefish overrides."""
    merged = dict(BANK_DEFINITIONS)
    merged["Eq8"] = _CUBEFISH_EQ8
    merged["FilterEQ3"] = _CUBEFISH_FILTEREQ3
    merged["Reverb"] = _CUBEFISH_REVERB
    merged["Delay"] = _CUBEFISH_DELAY
    return merged


CUBEFISH_BANK_DEFINITIONS = build_cubefish_bank_definitions()
