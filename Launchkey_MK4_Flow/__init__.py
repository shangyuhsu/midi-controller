"""Launchkey MK4 Flow - Ableton's own Launchkey MK4 script, plus a Flow page.

Everything Ableton's script does stays its own - faders, arm and select
buttons, encoder modes, transport, the screen, the drum layout and the DAW
pad layout's clip and sequencer pages. This adds one more page to that DAW
pad layout: "flow". Shift + the scene-launch button (">" right of the top
row of pads) switches to it and back to whichever page was showing.

On the flow page Ableton's code holds the 16 pads but does nothing with them -
no clip launching, no lights. Flow reads them over its own connection to the
Launchkey's DAW port and lights them in its bank colours. It learns which
page is showing from one word, "flow" or "live", written here to
/Users/Shared/Flow/Bridge/launchkey-page whenever that changes.

Set it in Live's Preferences > Link/Tempo/MIDI in place of "Launchkey MK4",
with the same DAW ports. Built on the decompiled script in
MIDIRemoteScripts/Launchkey_MK4: a Live update that reorganises it may break
this, which would show as a script error in Live's Log.txt.
"""
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
from Launchkey_MK4 import Launchkey_MK4, create_launchkey_specification, midi
from Launchkey_MK4.elements import Elements
from Launchkey_MK4.mappings import create_mappings
from ableton.v3.control_surface import Component
from ableton.v3.control_surface.capabilities import NOTES_CC, PORTS_KEY, SCRIPT, SYNC, inport, outport
from ableton.v3.control_surface.controls import ButtonControl, control_matrix
from ableton.v3.control_surface.mode import ImmediateBehaviour, make_reenter_behaviour

PAGE_FILE = "/Users/Shared/Flow/Bridge/launchkey-page"

# The v3 framework has no log_message (that is _Framework's): it logs through
# Python's logging, which Live writes to its Log.txt.
logger = logging.getLogger(__name__)


def get_capabilities():
    # Ableton's ports, but no controller id: Live must not pick this on its
    # own in place of the stock script, or load both.
    return {PORTS_KEY: [inport(props=[NOTES_CC]),
                        inport(props=[NOTES_CC, SCRIPT]),
                        outport(props=[]),
                        outport(props=[NOTES_CC, SYNC, SCRIPT])]}


class FlowElements(Elements):

    def __init__(self, *a, **k):
        super(FlowElements, self).__init__(*a, **k)
        # Shift + scene launch: unused by Ableton's script - the Flow toggle.
        self.add_shifted_control(self.scene_launch_button)


class FlowPageComponent(Component):
    """Holds the pads on the flow page, so Ableton's components let go of them.

    Colourless buttons send nothing to the pads: their lights are Flow's.
    """
    pads = control_matrix(ButtonControl, color=None)

    def __init__(self, *a, **k):
        super(FlowPageComponent, self).__init__(*a, name="Flow_Page", **k)


class FlowToggleComponent(Component):
    toggle_button = ButtonControl(color=None)

    def __init__(self, *a, **k):
        super(FlowToggleComponent, self).__init__(*a, name="Flow_Toggle", **k)
        self.control_surface = None

    @toggle_button.pressed
    def toggle_button(self, _):
        if self.control_surface is not None:
            self.control_surface.toggle_flow_page()


def create_flow_mappings(control_surface):
    mappings = create_mappings(control_surface)
    mappings["Daw_Pad_Modes"]["flow"] = dict(component="Flow_Page", pads="main_pads")
    mappings["Flow_Toggle"] = dict(toggle_button="scene_launch_button_with_shift")

    # Choosing the DAW layout again on the device flips clip and sequencer, as
    # before - never into the flow page, which only its own toggle reaches.
    def flip_clip_and_sequencer():
        daw = control_surface.component_map["Daw_Pad_Modes"]
        daw.selected_mode = "sequencer" if daw.selected_mode == "clip" else "clip"

    mappings["Main_Pad_Modes"]["daw"]["behaviour"] = make_reenter_behaviour(
        ImmediateBehaviour, on_reenter=flip_clip_and_sequencer)
    return mappings


class Launchkey_MK4_Flow(Launchkey_MK4):

    def setup(self):
        super(Launchkey_MK4_Flow, self).setup()
        self._flow_page_from = "clip"
        self._reported_page = None
        self.component_map["Flow_Toggle"].control_surface = self
        self.register_slot(self.component_map["Daw_Pad_Modes"], self._report_page, "selected_mode")
        self.register_slot(self.component_map["Main_Pad_Modes"], self._report_page, "selected_mode")
        self._report_page()

    def toggle_flow_page(self):
        # Only the DAW layout's pads are the script's to give; on Drum or a
        # Custom Mode the toggle does nothing.
        if self.component_map["Main_Pad_Modes"].selected_mode != "daw":
            return

        daw = self.component_map["Daw_Pad_Modes"]

        if daw.selected_mode == "flow":
            daw.selected_mode = self._flow_page_from or "clip"
        else:
            self._flow_page_from = daw.selected_mode
            daw.selected_mode = "flow"

    def _report_page(self, *_):
        on_flow = (self.component_map["Main_Pad_Modes"].selected_mode == "daw"
                   and self.component_map["Daw_Pad_Modes"].selected_mode == "flow")
        page = "flow" if on_flow else "live"

        if page == self._reported_page:
            return

        self._reported_page = page

        try:
            if not os.path.isdir(os.path.dirname(PAGE_FILE)):
                os.makedirs(os.path.dirname(PAGE_FILE))
            with open(PAGE_FILE, "w") as f:
                f.write(page + "\n")
            logger.info("Launchkey_MK4_Flow: pads are " + page + "'s")
        except Exception as e:
            logger.warning("Launchkey_MK4_Flow: could not write " + PAGE_FILE + ": " + str(e))

    def disconnect(self):
        # Gone: the pads are Live's again, as far as Flow is concerned.
        self._reported_page = None
        try:
            with open(PAGE_FILE, "w") as f:
                f.write("live\n")
        except Exception:
            pass
        super(Launchkey_MK4_Flow, self).disconnect()


def create_instance(c_instance):
    specification = create_launchkey_specification(FlowElements, create_flow_mappings, midi.MK4_SYSEX_HEADER)
    specification.component_map = dict(specification.component_map,
                                        Flow_Page=FlowPageComponent,
                                        Flow_Toggle=FlowToggleComponent)
    return Launchkey_MK4_Flow(specification=specification, c_instance=c_instance)
