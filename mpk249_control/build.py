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
DEV_W = 430
INSTALL = os.path.expanduser(
    "~/Music/Ableton/User Library/Presets/Audio Effects/Max Audio Effect/MPK249 Control")
REMOTE_SCRIPTS = "/Applications/Ableton Live 11 Suite.app/Contents/App-Resources/MIDI Remote Scripts"
SCRIPTS = ["mpk249.js", "mpk249-keys.js", "mpk249-events.jxa"]

# The MPK's pad colours, in the order of their codes (its manual's list).
COLOURS = ["Off", "Red", "Orange", "Amber", "Yellow", "Green", "Green Blue", "Aqua",
           "Light Blue", "Blue", "Purple", "Pink", "Hot Pink", "Light Purple",
           "Light Green", "Light Pink", "Grey"]

# What bank A had in the preset when this was written - the menus' defaults.
DEFAULT_COLOURS = [12, 12, 4, 2, 4, 15, 7, 15, 6, 15, 6, 7, 16, 16, 16, 16]
DEFAULT_PRESSED = 16
DEFAULT_SELECTED = 5    # Green

# What each pad does (mpk249.js's PAD_ACTIONS), shown under its menu.
PAD_LABELS = {13: "Track 1", 14: "Track 2", 15: "Track 3", 16: "Track 4",
              9: "Track 5", 10: "Track 6", 11: "Track 7", 12: "Track 8",
              5: "Plug-in", 6: "Select", 7: "Grid -", 8: "Grid +",
              1: "Metronome", 2: "Mute", 3: "Solo", 4: "Arm"}


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

    def menu(self, longname, shortname, rect, prect, initial):
        """A live.menu that is a Live parameter: saved with the set, recalled by presets."""
        i = self.shown({"maxclass": "live.menu", "numinlets": 1, "numoutlets": 3,
                        "outlettype": ["", "", "float"], "parameter_enable": 1, "varname": longname,
                        "fontsize": 9.0,
                        "saved_attribute_attributes": {"valueof": {
                            "parameter_longname": longname, "parameter_shortname": shortname,
                            "parameter_type": 2, "parameter_enum": COLOURS,
                            "parameter_mmax": len(COLOURS) - 1,
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

    js = p.obj("js mpk249.js", 200, 200, nin=1, nout=2, w=110)
    p.connect(ini, 0, js, 0)

    node = p.obj("node.script mpk249-keys.js @autostart 1 @watch 1", 200, 260, nin=1, nout=2, w=330)
    p.connect(js, 1, node, 0)

    p.label("MPK249 Control", [30, 330, 120, 18], [8, 4, 160, 18], size=11.0, bold=1)

    status = p.shown({"maxclass": "comment", "text": "Waiting for Live...", "numinlets": 1, "numoutlets": 0,
                      "fontsize": 9.5, "linecount": 4, "textcolor": [0.8, 0.8, 0.8, 1.0]},
                     [30, 360, 190, 60], [8, 24, 190, 60])
    p.connect(js, 0, status, 0)

    # The key helper's own line: whether macOS lets it post events.
    route = p.obj("route status", 200, 300, nin=2, nout=2)
    pset = p.obj("prepend set", 200, 330, nin=1, nout=1)
    keys_status = p.shown({"maxclass": "comment", "text": "", "numinlets": 1, "numoutlets": 0,
                           "fontsize": 9.5, "linecount": 2, "textcolor": [0.8, 0.8, 0.8, 1.0]},
                          [30, 430, 190, 34], [8, 88, 190, 34])
    p.connect(node, 0, route, 0)
    p.connect(route, 0, pset, 0)
    p.connect(pset, 0, keys_status, 0)

    rescan = p.shown({"maxclass": "live.text", "text": "Rescan", "mode": 0,
                      "numinlets": 1, "numoutlets": 2, "outlettype": ["", ""],
                      "parameter_enable": 1, "fontsize": 9.5,
                      "saved_attribute_attributes": {"valueof": {
                          "parameter_longname": "Rescan", "parameter_shortname": "Rescan",
                          "parameter_type": 2, "parameter_enum": ["off", "on"], "parameter_mmax": 1,
                          "parameter_invisible": 2}}},
                     [30, 480, 70, 20], [8, 130, 70, 20])
    p.params[rescan] = ["Rescan", "Rescan", 0]
    p.connect(rescan, 0, ini, 0)

    # Bank A's colours, laid out as the pads are: pad 13 top left, pad 1 bottom left.
    p.label("Pad colours (bank A)", [400, 330, 200, 18], [206, 4, 200, 16], size=9.5, bold=1)
    cell_w, cell_h, x0, y0 = 54, 30, 206, 20
    rows = [[13, 14, 15, 16], [9, 10, 11, 12], [5, 6, 7, 8], [1, 2, 3, 4]]

    for r, row in enumerate(rows):
        for c, pad in enumerate(row):
            px, py = x0 + c * cell_w, y0 + r * cell_h
            m = p.menu("Pad %d colour" % pad, "Pad %d" % pad,
                       [400 + c * 80, 360 + r * 60, 52, 16], [px, py, cell_w - 2, 15],
                       DEFAULT_COLOURS[pad - 1])
            p.label(PAD_LABELS.get(pad, ""), [400 + c * 80, 378 + r * 60, 60, 14], [px, py + 14, cell_w - 2, 14], size=8.0)
            pre = p.obj("prepend colour %d" % pad, 400 + c * 80, 395 + r * 60, nin=1, nout=1, w=110)
            p.connect(m, 0, pre, 0)
            p.connect(pre, 0, js, 0)

    # A pad held down, and the selected track's pad - each one colour for all.
    py = y0 + 4 * cell_h + 2

    for n, (text, longname, default, message) in enumerate(
            [("Pressed", "Pressed colour", DEFAULT_PRESSED, "pressed"),
             ("Selected", "Selected track colour", DEFAULT_SELECTED, "selected")]):
        px = x0 + n * 108
        p.label(text, [400 + n * 200, 620, 60, 16], [px, py, 44, 15], size=9.0)
        m = p.menu(longname, text, [460 + n * 200, 620, 80, 16], [px + 44, py, 62, 15], default)
        pre = p.obj("prepend " + message, 460 + n * 200, 650, nin=1, nout=1, w=110)
        p.connect(m, 0, pre, 0)
        p.connect(pre, 0, js, 0)

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
