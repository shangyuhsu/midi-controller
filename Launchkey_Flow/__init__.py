from __future__ import absolute_import, print_function, unicode_literals
from _Framework.Capabilities import NOTES_CC, PORTS_KEY, REMOTE, SCRIPT, inport
from .Launchkey_Flow import Launchkey_Flow


def get_capabilities():
    # No controller id: Live must never pick this on its own - the Launchkey's
    # own row belongs to Ableton's Launchkey MK4 script.
    return {PORTS_KEY: [inport(props=[NOTES_CC, SCRIPT, REMOTE])]}


def create_instance(c_instance):
    return Launchkey_Flow(c_instance)
