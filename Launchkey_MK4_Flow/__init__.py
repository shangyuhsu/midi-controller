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

The same toggle gives Flow the encoders' Plugin layout: there, with the toggle
on, Ableton's device control lets go of the eight encoders and its knob
readouts stay quiet, and Flow reads the encoders off the DAW port and fills
their displays itself. Off, the Plugin layout is Live's device control again,
its displays re-sent in full. Written for Flow to
/Users/Shared/Flow/Bridge/launchkey-encoders ("flow" or "live").

The toggle says "Mode / Flow" or "Mode / DAW" on the screen as it goes. In
the fader buttons' Arm layout a press also selects the track, as the Axiom's do.

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
from Launchkey_MK4.encoder_touch import EncoderTouchComponent
from Launchkey_MK4.mappings import create_mappings
from ableton.v3.control_surface import Component
from ableton.v3.control_surface.capabilities import NOTES_CC, PORTS_KEY, SCRIPT, SYNC, inport, outport
from ableton.v3.control_surface.controls import ButtonControl, EncoderControl, control_matrix
from ableton.v3.control_surface.display import Renderable
from ableton.v3.control_surface.mode import ImmediateBehaviour, make_reenter_behaviour
from ableton.v3.live import song

PAGE_FILE = "/Users/Shared/Flow/Bridge/launchkey-page"
ENCODERS_FILE = "/Users/Shared/Flow/Bridge/launchkey-encoders"

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


class FlowEncodersComponent(Component):
    """Holds the encoders in the Plugin layout's "flow" mode, so Ableton's
    device control lets go of them. They move nothing in Live: Flow reads them.
    """
    encoders = control_matrix(EncoderControl)

    def __init__(self, *a, **k):
        super(FlowEncodersComponent, self).__init__(*a, name="Flow_Encoders", **k)


class FlowEncoderTouchComponent(EncoderTouchComponent):
    """Ableton's, but quiet while Flow has the encoders: a released encoder
    is what makes the script write its readout, and it would write "-" over
    the text Flow keeps there.
    """
    flow_owns_encoders = False

    def _set_released(self, index):
        if not self.flow_owns_encoders:
            super(FlowEncoderTouchComponent, self)._set_released(index)


class FlowToggleComponent(Component, Renderable):
    toggle_button = ButtonControl(color=None)

    def __init__(self, *a, **k):
        super(FlowToggleComponent, self).__init__(*a, name="Flow_Toggle", **k)
        self.control_surface = None

    @toggle_button.pressed
    def toggle_button(self, _):
        if self.control_surface is not None:
            to_flow = self.control_surface.toggle_flow_page()
            # The screen says which way it went, as the script's own mode changes do.
            self.notify(self.notifications.generic, "Mode\n" + ("Flow" if to_flow else "DAW"))


def create_flow_mappings(control_surface):
    mappings = create_mappings(control_surface)
    mappings["Daw_Pad_Modes"]["flow"] = dict(component="Flow_Page", pads="main_pads")
    mappings["Flow_Toggle"] = dict(toggle_button="scene_launch_button_with_shift")

    # The Plugin layout becomes two: Ableton's device control, or Flow's.
    plugin = mappings["Main_Encoder_Modes"]["plugin"]
    mappings["Plugin_Encoder_Modes"] = dict(enable=False,
                                            is_private=True,
                                            live=dict(modes=[m for m in plugin["modes"] if isinstance(m, dict)]),
                                            flow=dict(component="Flow_Encoders", encoders="encoders"))
    mappings["Main_Encoder_Modes"]["plugin"] = dict(
        modes=[dict(component="Plugin_Encoder_Modes")] + [m for m in plugin["modes"] if not isinstance(m, dict)],
        behaviour=plugin["behaviour"])

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
        self._reported_encoders = None
        for button in self.elements.fader_buttons_raw:
            button.add_value_listener(self._on_fader_button, identify_sender=True)
        self.register_slot(self.component_map["Main_Encoder_Modes"], self._report_encoders, "selected_mode")
        self._report_encoders()

    def toggle_flow_page(self):
        """Returns True when the toggle went to Flow."""
        # The encoders' Plugin layout follows the toggle whatever the pads show.
        to_flow = self._toggle_flow_encoders()

        # Only the DAW layout's pads are the script's to give; on Drum or a
        # Custom Mode the toggle does nothing more.
        if self.component_map["Main_Pad_Modes"].selected_mode != "daw":
            return to_flow

        daw = self.component_map["Daw_Pad_Modes"]

        # Pads follow the encoders, so the two never end up on opposite sides.
        if not to_flow:
            # Each pad remembers the last colour sent it and skips sending it
            # again - but Flow coloured them since, so coming back the clip
            # page sent nothing and Flow's colours stayed. Forgotten first.
            for pad in self.elements.main_pads:
                pad.clear_send_cache()

            if daw.selected_mode == "flow":
                daw.selected_mode = self._flow_page_from or "clip"
        elif daw.selected_mode != "flow":
            self._flow_page_from = daw.selected_mode
            daw.selected_mode = "flow"

        return to_flow

    def _on_fader_button(self, value, sender):
        """In the Arm layout a press arms (Ableton's mixer does that) and also
        selects the track. Select layout is untouched."""
        if not value or self.component_map["Fader_Button_Modes"].selected_mode != "arm":
            return

        index = list(self.elements.fader_buttons_raw).index(sender)
        track = self.component_map["Mixer"].channel_strip(index).track

        if track is not None:
            song().view.selected_track = track

    def _toggle_flow_encoders(self):
        modes = self.component_map["Plugin_Encoder_Modes"]
        to_flow = modes.selected_mode != "flow"
        modes.selected_mode = "flow" if to_flow else "live"
        self._report_encoders()
        return to_flow

    def _report_encoders(self, *_):
        """Flow's only while the toggle is on AND the Plugin layout is up -
        Flow cannot tell the layout itself (the device reports it only as it
        changes), and on Mixer or Sends the encoders stay Live's whatever the
        toggle says.
        """
        owner = ("flow" if self.component_map["Plugin_Encoder_Modes"].selected_mode == "flow"
                 and self.component_map["Main_Encoder_Modes"].selected_mode == "plugin" else "live")
        self.component_map["Encoder_Touch"].flow_owns_encoders = owner == "flow"

        if owner == self._reported_encoders:
            return

        if owner == "live" and self._reported_encoders == "flow":
            # Flow wrote these displays meanwhile; each remembers what it last
            # sent and skips sending it again, so forget it all and resend.
            for i in range(8):
                getattr(self.elements, "encoder_{}_display_command".format(i)).clear_send_cache()

        self._reported_encoders = owner
        self._write_bridge(ENCODERS_FILE, owner)

    def _write_bridge(self, path, word):
        try:
            if not os.path.isdir(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))
            with open(path, "w") as f:
                f.write(word + "\n")
            logger.info("Launchkey_MK4_Flow: " + os.path.basename(path) + " " + word)
        except Exception as e:
            logger.warning("Launchkey_MK4_Flow: could not write " + path + ": " + str(e))

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
        for button in self.elements.fader_buttons_raw:
            if button.value_has_listener(self._on_fader_button):
                button.remove_value_listener(self._on_fader_button)

        # Gone: the pads are Live's again, as far as Flow is concerned.
        self._reported_page = None
        for path in (PAGE_FILE, ENCODERS_FILE):
            try:
                with open(path, "w") as f:
                    f.write("live\n")
            except Exception:
                pass
        super(Launchkey_MK4_Flow, self).disconnect()


def create_instance(c_instance):
    specification = create_launchkey_specification(FlowElements, create_flow_mappings, midi.MK4_SYSEX_HEADER)
    specification.component_map = dict(specification.component_map,
                                        Flow_Page=FlowPageComponent,
                                        Flow_Toggle=FlowToggleComponent,
                                        Flow_Encoders=FlowEncodersComponent,
                                        Encoder_Touch=FlowEncoderTouchComponent)
    return Launchkey_MK4_Flow(specification=specification, c_instance=c_instance)
