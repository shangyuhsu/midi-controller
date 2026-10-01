/*  MPK249 Control's hands on the keyboard and mouse - Node for Max.

    For what Live's API cannot do: the arrangement grid size and the plug-in
    windows have only keyboard shortcuts, and nothing scrolls a view without
    moving the selection. mpk249.js asks; this has macOS post the event.

    The posting is done by mpk249-events.jxa, run once by osascript and fed a
    line per event - starting osascript for each one would lag a knob. macOS
    asks once for Accessibility permission for it (System Settings > Privacy &
    Security > Accessibility); until it is granted, events are dropped.

    Keystrokes go to whatever app is in front - Live, as you play it.
*/

const maxApi = require("max-api");
const { spawn } = require("child_process");
const path = require("path");

// Key codes are the US layout's, which shortcuts follow on any layout.
const KEYS = {
    gridFiner:    { code: 18, mods: "cmd" },        // Cmd-1  Narrow Grid
    gridCoarser:  { code: 19, mods: "cmd" },        // Cmd-2  Widen Grid
    pluginWindow: { code: 35, mods: "cmd,alt" },    // Cmd-Alt-P  Show/Hide Plug-In Windows
};

let helper = null;

function status(text) {
    maxApi.outlet("status", text);
}

function start() {
    helper = spawn("/usr/bin/osascript", ["-l", "JavaScript", path.join(__dirname, "mpk249-events.jxa")]);

    let pending = "";

    helper.stderr.on("data", (data) => {
        pending += data.toString();
        const lines = pending.split("\n");
        pending = lines.pop();

        for (const line of lines.filter(Boolean)) {
            maxApi.post("mpk249-events: " + line);

            if (line.startsWith("trusted"))
                status(line === "trusted yes" ? "Keys and scrolling: ready."
                                              : "Keys and scrolling need Accessibility permission for Live.");
        }
    });

    helper.on("exit", (code) => {
        maxApi.post("mpk249-events stopped (" + code + ")");
        helper = null;
    });
}

function send(line) {
    if (helper === null)
        start();

    helper.stdin.write(line + "\n");
}

maxApi.addHandler("key", (name) => {
    const key = KEYS[name];

    if (key)
        send("key " + key.code + " " + key.mods);
});

maxApi.addHandler("hscroll", (lines) => {
    if (lines)
        send("hscroll " + Math.round(lines));
});

start();
