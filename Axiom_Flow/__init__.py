from __future__ import absolute_import, print_function, unicode_literals
from _Framework.Capabilities import NOTES_CC, PORTS_KEY, REMOTE, SCRIPT, inport, outport
from .Axiom_Flow import Axiom_Flow


def get_capabilities():
    # No controller id: Live would otherwise put Axiom_DirectLink on the
    # Axiom by itself. This row is chosen by hand, on the DirectLink ports.
    return {PORTS_KEY: [inport(props=[NOTES_CC, SCRIPT, REMOTE]),
                        outport(props=[SCRIPT, REMOTE])]}


def create_instance(c_instance):
    return Axiom_Flow(c_instance)
