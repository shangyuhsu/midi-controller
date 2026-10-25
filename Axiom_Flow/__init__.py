from __future__ import absolute_import, print_function, unicode_literals
from _Framework.Capabilities import NOTES_CC, PORTS_KEY, REMOTE, SCRIPT, inport
from .Axiom_Flow import Axiom_Flow


def get_capabilities():
    # No controller id: Live must never pick this on its own - its row is
    # chosen by hand, and Live's Axiom_DirectLink must stay off the Axiom.
    return {PORTS_KEY: [inport(props=[NOTES_CC, SCRIPT, REMOTE])]}


def create_instance(c_instance):
    return Axiom_Flow(c_instance)
