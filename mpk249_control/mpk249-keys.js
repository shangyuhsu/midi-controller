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
const fs = require("fs");
const os = require("os");
const path = require("path");

// Every request and every reply from the poster, for when something goes quiet.
const LOG = path.join(os.homedir(), "Library", "Logs", "MPK249 Control.log");
fs.writeFileSync(LOG, "MPK249 Control started " + new Date().toISOString() + "\n");

function log(line) {
    fs.appendFile(LOG, new Date().toISOString().slice(11, 23) + "  " + line + "\n", () => {});
}

// Key codes are the US layout's, which shortcuts follow on any layout.
const KEYS = {
    gridFiner:    { code: 18, mods: "cmd" },        // Cmd-1  Narrow Grid
    gridCoarser:  { code: 19, mods: "cmd" },        // Cmd-2  Widen Grid
    pluginWindow: { code: 35, mods: "cmd,alt" },    // Cmd-Alt-P  Show/Hide Plug-In Windows
    loopSelection: { code: 37, mods: "cmd" },       // Cmd-L  Loop Selection
    left:         { code: 123, mods: "-" },         // the arrow keys: insert marker and start marker
    right:        { code: 124, mods: "-" },
    shiftLeft:    { code: 123, mods: "shift" },     // ...growing the time selection
    shiftRight:   { code: 124, mods: "shift" },
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
            log("poster: " + line);

            if (line.startsWith("trusted"))
                status(line === "trusted yes" ? "Keys and scrolling: ready."
                                              : "Keys and scrolling need Accessibility permission for Live.");
        }
    });

    helper.on("exit", (code) => {
        maxApi.post("mpk249-events stopped (" + code + ")");
        log("poster stopped (" + code + ")");
        helper = null;
    });
}

function send(line) {
    log("-> " + line);

    if (helper === null)
        start();

    helper.stdin.write(line + "\n");
}

maxApi.addHandler("key", (name) => {
    const key = KEYS[name];

    if (!key)
        log("no key named " + name);

    if (key)
        send("key " + key.code + " " + key.mods);
});

// The device's own lines, into the same log.
maxApi.addHandler("log", (...words) => log("device: " + words.join(" ")));

maxApi.addHandler("hscroll", (amount, style) => {
    if (amount)
        send("hscroll " + Math.round(amount) + " " + (style || "line"));
});

start();
