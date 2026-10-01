#!/usr/bin/env python3
"""Generate 'MPK249 Control.amxd', the Max for Live half of the MPK249 setup:
what Port A's pads and knobs do in Live, and bank A's pad colours. See
mpk249.js, and ../MPK249_Flow for the remote script that claims the controls.

    python3 build.py [--install]

--install puts the device in Live's User Library (Max Audio Effect) with its
scripts SYMLINKED back here, so editing mpk249.js or mpk249-keys.js in this
repo changes the device in Live at once (both reload when saved); and links
the remote script into Live's MIDI Remote Scripts, as cubefish is.

An audio effect so it can sit on the master track: one device for the set.
Sound passes straight through. The .amxd format: three chunks, then the
patcher JSON (as Flow's Tools/FlowBake and Tools/MidiTranslator write it).
"""
import json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEV_W = 688
INSTALL = os.path.expanduser(
    "~/Music/Ableton/User Library/Presets/Audio Effects/Max Audio Effect/MPK249 Control")
REMOTE_SCRIPTS = "/Applications/Ableton Live 11 Suite.app/Contents/App-Resources/MIDI Remote Scripts"
SCRIPTS = ["mpk249.js", "mpk249-keys.js", "mpk249-events.jxa"]

# The MPK's pad colours, in the order of their codes (its manual's list), named short
# enough for two menus to a pad. Off - unlit - is a colour like any other.
COLOURS = ["Off", "Red", "Orange", "Amber", "Yellow", "Green", "GrnBlue", "Aqua",
           "LtBlue", "Blue", "Purple", "Pink", "HotPink", "LtPurple",
           "LtGreen", "LtPink", "Grey"]

# The menus' defaults, by pad - kept the same as mpk249.js's padColours / litColours.
DEFAULT_COLOURS = [16, 16, 16, 16, 4, 15, 7, 15, 16, 16, 16, 16, 16, 16, 16, 16]
DEFAULT_LIT = [4, 2, 8, 1, 0, 0, 0, 0, 5, 5, 5, 5, 5, 5, 5, 5]
DEFAULT_PRESSED = 16

# What each pad does (mpk249.js's PAD_ACTIONS), shown under its menus.
PAD_LABELS = {13: "Track 1", 14: "Track 2", 15: "Track 3", 16: "Track 4",
              9: "Track 5", 10: "Track 6", 11: "Track 7", 12: "Track 8",
              5: "Plug-in", 6: "Select", 7: "Grid -", 8: "Grid +",
              1: "Metronome", 2: "Mute", 3: "Solo", 4: "Arm"}

# Pads with a state to show - selected, or on - and so a lit colour.
LIT_PADS = {1, 2, 3, 4, 9, 10, 11, 12, 13, 14, 15, 16}

CURSOR_STEPS = ["1/32", "1/16", "1/8", "1/4", "1/2", "1 bar", "2 bars", "4 bars", "8 bars"]   # mpk249.js's CURSOR_STEPS
DEFAULT_STEP = 1
DEFAULT_DETENTS = {"cursor": 2, "sideScroll": 1, "zoom": 2}


class Patcher:
    def __init__(self):
        self.boxes, self.lines, self.params, self._n = [], [], {}, 0

    def add(self, box):
        self._n += 1
        box["id"] = "obj-%d" % self._n
        self.boxes.append({"box": box})
        return box["id"]

    def obj(self, text, x, y, nin=1, nout=0, w=None):
        b = {"maxclass": "newobj", "text": text,
             "patching_rect": [x, y, w or max(40, 8 * len(text) + 16), 22],
             "numinlets": nin, "numoutlets": nout}
        if nout:
            b["outlettype"] = [""] * nout
        return self.add(b)

    def msg(self, text, x, y):
        return self.add({"maxclass": "message", "text": text,
                         "patching_rect": [x, y, max(28, 8 * len(text) + 12), 22],
                         "numinlets": 2, "numoutlets": 1, "outlettype": [""]})

    def shown(self, box, rect, prect):
        box.update({"patching_rect": rect, "presentation": 1, "presentation_rect": prect})
        return self.add(box)

    def label(self, text, rect, prect, size=9.0, bold=0):
        return self.shown({"maxclass": "live.comment", "text": text, "numinlets": 1, "numoutlets": 0,
                           "fontsize": size, "fontface": bold}, rect, prect)

    def menu(self, longname, shortname, rect, prect, initial, items=COLOURS):
        """A live.menu that is a Live parameter: saved with the set, recalled by presets."""
        i = self.shown({"maxclass": "live.menu", "numinlets": 1, "numoutlets": 3,
                        "outlettype": ["", "", "float"], "parameter_enable": 1, "varname": longname,
                        "fontsize": 9.0,
                        "saved_attribute_attributes": {"valueof": {
                            "parameter_longname": longname, "parameter_shortname": shortname,
                            "parameter_type": 2, "parameter_enum": items,
                            "parameter_mmax": len(items) - 1,
                            "parameter_initial": [initial], "parameter_initial_enable": 1,
                            "parameter_invisible": 1}}},
                       rect, prect)
        self.params[i] = [longname, shortname, 0]
        return i

    def numbox(self, longname, shortname, rect, prect, initial, low, high):
        i = self.shown({"maxclass": "live.numbox", "numinlets": 1, "numoutlets": 2,
                        "outlettype": ["", "float"], "parameter_enable": 1, "varname": longname,
                        "fontsize": 9.0,
                        "saved_attribute_attributes": {"valueof": {
                            "parameter_longname": longname, "parameter_shortname": shortname,
                            "parameter_type": 1, "parameter_mmin": low, "parameter_mmax": high,
                            "parameter_initial": [initial], "parameter_initial_enable": 1,
                            "parameter_invisible": 1}}},
                       rect, prect)
        self.params[i] = [longname, shortname, 0]
        return i

    def connect(self, src, sout, dst, din):
        self.lines.append({"patchline": {"source": [src, sout], "destination": [dst, din]}})


def build():
    p = Patcher()

    # Sound straight through: it is on the master for the set, not for audio.
    pin = p.obj("plugin~ 2", 30, 30, nin=2, nout=2)
    pout = p.obj("plugout~ 2", 30, 70, nin=2, nout=0)
    p.boxes[-2]["box"]["outlettype"] = ["signal", "signal"]
    p.connect(pin, 0, pout, 0)
    p.connect(pin, 1, pout, 1)

    # Live's API is only usable once the device is fully loaded.
    ld = p.obj("live.thisdevice", 200, 30, nin=1, nout=3)
    tb = p.obj("t b", 200, 60, nin=1, nout=1)
    dl = p.obj("delay 500", 200, 90, nin=2, nout=1)
    ini = p.msg("init", 200, 120)
    p.connect(ld, 0, tb, 0)
    p.connect(tb, 0, dl, 0)
    p.connect(dl, 0, ini, 0)

    js = p.obj("js mpk249.js", 200, 200, nin=1, nout=3, w=110)
    p.connect(ini, 0, js, 0)

    node = p.obj("node.script mpk249-keys.js @autostart 1 @watch 1", 200, 260, nin=1, nout=2, w=330)
    p.connect(js, 1, node, 0)

    p.label("MPK249 Control", [30, 330, 120, 18], [8, 4, 160, 18], size=11.0, bold=1)

    status = p.shown({"maxclass": "comment", "text": "Waiting for Live...", "numinlets": 1, "numoutlets": 0,
                      "fontsize": 9.0, "linecount": 3, "textcolor": [0.8, 0.8, 0.8, 1.0]},
                     [30, 360, 190, 44], [8, 22, 250, 44])
    p.connect(js, 0, status, 0)

    # The key helper's own line: whether macOS lets it post events.
    route = p.obj("route status", 200, 300, nin=2, nout=2)
    pset = p.obj("prepend set", 200, 330, nin=1, nout=1)
    keys_status = p.shown({"maxclass": "comment", "text": "", "numinlets": 1, "numoutlets": 0,
                           "fontsize": 9.0, "linecount": 2, "textcolor": [0.8, 0.8, 0.8, 1.0]},
                          [30, 410, 190, 24], [8, 66, 250, 24])
    p.connect(node, 0, route, 0)
    p.connect(route, 0, pset, 0)
    p.connect(pset, 0, keys_status, 0)

    def to_js(widget, message, x, y):
        pre = p.obj("prepend " + message, x, y, nin=1, nout=1, w=150)
        p.connect(widget, 0, pre, 0)
        p.connect(pre, 0, js, 0)

    # What the cursor knob moves, and the start marker's step.
    p.label("Cursor", [30, 450, 34, 15], [8, 93, 34, 15], size=9.0)
    mode = p.menu("Cursor moves", "Cursor", [64, 450, 56, 15], [42, 93, 54, 15], 0, items=["Both", "Arrows", "Start"])
    to_js(mode, "cursormode", 64, 470)
    p.label("Step", [130, 450, 26, 15], [102, 93, 26, 15], size=9.0)
    step = p.menu("Cursor step", "Step", [156, 450, 60, 15], [128, 93, 64, 15], DEFAULT_STEP, items=CURSOR_STEPS)
    to_js(step, "cursorstep", 156, 470)
    p.connect(js, 2, step, 0)      # the grid pads move Step with the grid

    # The view knobs: how many detents make one step.
    p.label("Detents", [30, 500, 44, 15], [8, 111, 42, 15], size=9.0)
    for n, (name, text) in enumerate([("cursor", "Cursor"), ("sideScroll", "Scroll"), ("zoom", "Zoom")]):
        px = 50 + n * 70
        p.label(text, [80 + n * 90, 500, 36, 15], [px, 111, 36, 15], size=9.0)
        nb = p.numbox(text + " detents", text, [116 + n * 90, 500, 28, 15], [px + 36, 111, 28, 15],
                      DEFAULT_DETENTS[name], 1, 16)
        to_js(nb, "detents " + name, 116 + n * 90, 520)

    # The side scroll: which kind of scroll event, and how far a step goes.
    p.label("Scroll", [30, 545, 34, 15], [8, 130, 34, 15], size=9.0)
    style = p.menu("Scroll style", "Scroll", [64, 545, 60, 15], [42, 130, 64, 15], 0,
                   items=["Pixels", "Shift+wheel", "Lines"])
    to_js(style, "scrollstyle", 64, 565)
    p.label("Amount", [130, 545, 40, 15], [112, 130, 40, 15], size=9.0)
    amount = p.numbox("Scroll amount", "Amount", [170, 545, 34, 15], [152, 130, 36, 15], 40, 1, 400)
    to_js(amount, "scrollamount", 170, 565)

    rescan = p.shown({"maxclass": "live.text", "text": "Rescan", "mode": 0,
                      "numinlets": 1, "numoutlets": 2, "outlettype": ["", ""],
                      "parameter_enable": 1, "fontsize": 9.0,
                      "saved_attribute_attributes": {"valueof": {
                          "parameter_longname": "Rescan", "parameter_shortname": "Rescan",
                          "parameter_type": 2, "parameter_enum": ["off", "on"], "parameter_mmax": 1,
                          "parameter_invisible": 2}}},
                     [30, 580, 60, 18], [8, 149, 60, 16])
    p.params[rescan] = ["Rescan", "Rescan", 0]
    p.connect(rescan, 0, ini, 0)

    # A pad held down: one colour for all.
    p.label("Pressed", [130, 580, 44, 15], [76, 150, 44, 15], size=9.0)
    pm = p.menu("Pressed colour", "Pressed", [174, 580, 56, 15], [120, 150, 72, 15], DEFAULT_PRESSED)
    to_js(pm, "pressed", 174, 600)

    # Bank A's colours, laid out as the pads are: pad 13 top left, pad 1 bottom left.
    # Each pad: its colour, and - for a pad that shows a state - its lit colour beside it.
    p.label("Pad colour  |  lit colour (selected / on)", [400, 330, 260, 16], [266, 3, 300, 15], size=9.0, bold=1)
    cell_w, cell_h, menu_w, x0, y0 = 104, 36, 50, 266, 20
    rows = [[13, 14, 15, 16], [9, 10, 11, 12], [5, 6, 7, 8], [1, 2, 3, 4]]

    for r, row in enumerate(rows):
        for c, pad in enumerate(row):
            px, py = x0 + c * cell_w, y0 + r * cell_h
            bx, by = 400 + c * 230, 360 + r * 80
            m = p.menu("Pad %d colour" % pad, "Pad %d" % pad, [bx, by, menu_w, 15], [px, py, menu_w, 15],
                       DEFAULT_COLOURS[pad - 1])
            to_js(m, "colour %d" % pad, bx, by + 40)

            if pad in LIT_PADS:
                lm = p.menu("Pad %d lit colour" % pad, "Pad %d lit" % pad, [bx + 110, by, menu_w, 15],
                            [px + menu_w + 2, py, menu_w, 15], DEFAULT_LIT[pad - 1])
                to_js(lm, "lit %d" % pad, bx + 110, by + 40)

            p.label(PAD_LABELS.get(pad, ""), [bx, by + 18, 100, 13], [px, py + 16, cell_w - 4, 13], size=8.0)

    params = dict(p.params)
    params["inherited_shortname"] = 1

    patcher = {
        "fileversion": 1,
        "appversion": {"major": 8, "minor": 5, "revision": 8, "architecture": "x64", "modernui": 1},
        "classnamespace": "box",
        "rect": [60.0, 80.0, 1000.0, 720.0],
        "openrect": [0.0, 0.0, float(DEV_W), 169.0],
        "bglocked": 0,
        "openinpresentation": 1,
        "default_fontsize": 12.0,
        "default_fontface": 0,
        "default_fontname": "Arial",
        "gridonopen": 1,
        "gridsize": [15.0, 15.0],
        "gridsnaponopen": 1,
        "objectsnaponopen": 1,
        "statusbarvisible": 2,
        "toolbarvisible": 1,
        "boxanimatetime": 200,
        "enablehscroll": 1,
        "enablevscroll": 1,
        "devicewidth": float(DEV_W),
        "description": "MPK249 Port A's pads and knobs in Live, and bank A's pad colours",
        "digest": "",
        "tags": "",
        "style": "",
        "boxes": p.boxes,
        "lines": p.lines,
        "parameters": params,
        # Where Max finds the scripts: beside the device.
        "dependency_cache": [{"name": name, "bootpath": INSTALL.replace(os.path.expanduser("~"), "~"),
                              "type": "TEXT", "implicit": 1} for name in SCRIPTS],
        "latency": 0,
        "is_mpe": 0,
        "platform_compatibility": 0,
        "project": {
            "version": 1, "creationdate": 3590052786, "modificationdate": 3590052786,
            "viewrect": [0.0, 0.0, 300.0, 500.0], "autoorganize": 1, "hideprojectwindow": 1,
            "showdependencies": 1, "autolocalize": 0, "contents": {"patchers": {}},
            "layout": {}, "searchpath": {}, "detailsvisible": 0,
            "amxdtype": 1633771873, "readonly": 0, "devpathtype": 0, "devpath": ".",
            "sortmode": 0, "viewmode": 0,
        },
        "autosave": 0,
    }
    return {"patcher": patcher}


def write_amxd(path, patch):
    js = json.dumps(patch, indent=1).encode("utf-8") + b"\x00"
    out = b"ampf" + struct.pack("<I", 4) + b"aaaa"
    out += b"meta" + struct.pack("<I", 4) + b"\x00\x00\x00\x00"
    out += b"ptch" + struct.pack("<I", len(js)) + js
    with open(path, "wb") as f:
        f.write(out)


def link(target, link_path):
    """A symlink at link_path to target - replacing an older link, never a real file."""
    if os.path.islink(link_path):
        os.remove(link_path)
    elif os.path.exists(link_path):
        raise SystemExit("%s exists and is not a link - not replacing it" % link_path)
    os.symlink(target, link_path)


if __name__ == "__main__":
    device = os.path.join(HERE, "MPK249 Control.amxd")
    write_amxd(device, build())
    print("wrote", device)

    if "--install" in sys.argv:
        os.makedirs(INSTALL, exist_ok=True)
        with open(device, "rb") as src, open(os.path.join(INSTALL, "MPK249 Control.amxd"), "wb") as dst:
            dst.write(src.read())
        for name in SCRIPTS:
            link(os.path.join(HERE, name), os.path.join(INSTALL, name))
        print("installed in", INSTALL, "(scripts linked to this repo)")

        link(os.path.join(REPO, "MPK249_Flow"), os.path.join(REMOTE_SCRIPTS, "MPK249_Flow"))
        print("linked the remote script into", REMOTE_SCRIPTS)
