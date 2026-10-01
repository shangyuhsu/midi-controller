/*  MPK249 Control - what Port A's pads and knobs do in Live.

    The MPK249_Flow remote script claims them (so their MIDI never reaches a
    track) and names them Pad_1..Pad_16, Encoder_1..Encoder_8. This device -
    an audio effect, on the master track - finds that script among Live's
    control surfaces, grabs those controls and observes their values. All the
    behaviour is here, so it can change without restarting Live: save this
    file and it reloads (autowatch).

    Pad colours: the device's menus set bank A's colours in the MPK's loaded
    preset, by SysEx sent through the remote script (send_midi) - which needs
    the script's OUTPUT to be "MPK249 (Remote)", the one port that takes it.
    Akai does not document the SysEx; see Flow's AGENTS.md (MPK249) for how
    it was found. They are sent again whenever the device loads, since the
    MPK forgets them when its preset changes.

    What Live's API cannot do - the arrangement grid size, a plugin window,
    scrolling the arrangement sideways - goes to mpk249-keys.js (Node for
    Max), which has macOS post the keystroke or scroll for it.

    Pads are Akai's numbering: 1 bottom left, 13 top left.

    Max's js is an old JavaScript: no let, const or arrow functions.
*/

autowatch = 1;
inlets = 1;
outlets = 2;        // 0: the status line   1: requests for mpk249-keys.js

var SURFACE_TYPE = "MPK249_Flow";

//==============================================================================
// What each control does - the place to change things.

var PAD_ACTIONS = {
    // Top two rows: select tracks 1-8, reading order.
    13: ["track", 1], 14: ["track", 2], 15: ["track", 3], 16: ["track", 4],
     9: ["track", 5], 10: ["track", 6], 11: ["track", 7], 12: ["track", 8],

    // Third row.
    5: ["pluginWindow"],    // Cmd-Alt-P: show/hide the plug-in windows
    6: ["select"],          // held: the cursor knob extends the time selection
    7: ["gridCoarser"],     // Cmd-2: widen the grid
    8: ["gridFiner"],       // Cmd-1: narrow the grid

    // Bottom row: the selected track, and the metronome.
    1: ["metronome"],
    2: ["mute"],
    3: ["solo"],
    4: ["arm"]
};

var ENCODER_ACTIONS = {
    1: "cursor",            // the insert marker, a grid step per detent
    2: "sideScroll",        // the arrangement, sideways
    3: "zoom",              // the arrangement, horizontally
    4: "volume",            // selected track
    5: "pan",               // selected track
    6: "send1",             // selected track
    7: "cueVolume",
    8: "masterVolume"
};

var PARAM_STEP = 0.005;         // of a parameter's range, per knob step
var MAX_VIEW_STEPS = 4;         // grid steps or zoom steps from one fast turn
var SIDE_SCROLL_LINES = 2;      // scroll lines per knob step
var SIDE_SCROLL_SIGN = -1;      // flip if turning right scrolls left
var ZOOM_IN = 3, ZOOM_OUT = 2;  // zoom_view directions; swap if backwards

// Bank A's pad colours in the MPK's memory, Akai pad order: unpressed, pressed.
var COLOUR_ADDRESS_OFF = 0x57c;
var COLOUR_ADDRESS_ON = 0x5bc;

//==============================================================================

var surface = null;
var observers = [];
var selectHeld = false;

// Set by the device's menus (colour codes 0-16, as the MPK's manual lists them).
var padColours = [12, 12, 4, 2, 4, 15, 7, 15, 6, 15, 6, 7, 16, 16, 16, 16];
var pressedColour = 16;

function status (text)
{
    outlet (0, "set", text);
}

function post_ (text)
{
    post ("MPK249 Control: " + text + "\n");
}

function idsOf (list)
{
    var ids = [];

    for (var i = 0; i + 1 < list.length; i += 2)
        if (list[i] == "id" && list[i + 1] != 0)
            ids.push (list[i + 1]);

    return ids;
}

function findSurface ()
{
    var app = new LiveAPI ("live_app");
    var count = app.getcount ("control_surfaces");

    for (var i = 0; i < count; ++i)
    {
        var cs = new LiveAPI ("live_app control_surfaces " + i);

        if (cs.id != 0 && cs.type == SURFACE_TYPE)
            return cs;
    }

    return null;
}

function release ()
{
    for (var i = 0; i < observers.length; ++i)
        observers[i].property = "";

    observers = [];
    selectHeld = false;
}

// Grabs one of the script's controls and calls handler (value) for each message from it.
function watch (name, handler)
{
    var reply = surface.call ("get_control", name);
    var ids = idsOf (reply);

    if (ids.length == 0)
    {
        post_ ("the script has no control " + name);
        return false;
    }

    surface.call ("grab_control", name);

    // The first call reports the value the control already has - not a message.
    var primed = false;

    var observer = new LiveAPI (function (args)
    {
        if (args[0] != "value")
            return;

        if (! primed)
        {
            primed = true;
            return;
        }

        try { handler (Number (args[1])); }
        catch (e) { post_ (name + ": " + e); }
    }, "id " + ids[0]);

    observer.property = "value";
    observers.push (observer);
    return true;
}

function init ()
{
    release ();
    surface = findSurface ();

    if (surface == null)
    {
        status ("No MPK249_Flow control surface. Set it in Preferences > Link/Tempo/MIDI, input and output MPK249 (Port A).");
        return;
    }

    var ok = 0;

    for (var p = 1; p <= 16; ++p)
        ok += watch ("Pad_" + p, padHandler (p)) ? 1 : 0;

    for (var e = 1; e <= 8; ++e)
        ok += watch ("Encoder_" + e, encoderHandler (e)) ? 1 : 0;

    status ("MPK249 Port A: " + ok + " of 24 controls.");
    sendColours ();
}

// Reloaded by autowatch while already running in Live: take the controls again.
var reloadTask = new Task (function ()
{
    try
    {
        if (new LiveAPI ("live_set").id != 0)
            init ();
    }
    catch (e) {}
});

reloadTask.schedule (300);

//==============================================================================
// Pads

function padHandler (pad)
{
    return function (value)
    {
        var action = PAD_ACTIONS[pad];

        if (action == null)
            return;

        // The one pad that matters on release.
        if (action[0] == "select")
        {
            selectHeld = value > 0;
            return;
        }

        if (value > 0)
            runPad (action);
    };
}

function runPad (action)
{
    switch (action[0])
    {
        case "track":           selectTrack (action[1]); break;
        case "pluginWindow":    outlet (1, "key", "pluginWindow"); break;
        case "gridCoarser":     outlet (1, "key", "gridCoarser"); break;
        case "gridFiner":       outlet (1, "key", "gridFiner"); break;
        case "metronome":       toggle (new LiveAPI ("live_set"), "metronome"); break;
        case "mute":            toggleOnTrack ("mute"); break;
        case "solo":            toggleOnTrack ("solo"); break;
        case "arm":             toggleOnTrack ("arm"); break;
    }
}

function selectTrack (number)
{
    var tracks = idsOf (new LiveAPI ("live_set").get ("visible_tracks"));

    if (number <= tracks.length)
        new LiveAPI ("live_set view").set ("selected_track", "id", tracks[number - 1]);
}

function toggle (api, property)
{
    api.set (property, Number (api.get (property)) ? 0 : 1);
}

function selectedTrack ()
{
    var track = new LiveAPI ("live_set view selected_track");
    return track.id != 0 ? track : null;
}

function isMaster (track)
{
    return track.id == new LiveAPI ("live_set master_track").id;
}

function toggleOnTrack (property)
{
    var track = selectedTrack ();

    // The master has no mute, solo or arm; a return track has no arm.
    if (track == null || isMaster (track))
        return;

    if (property == "arm" && ! Number (track.get ("can_be_armed")))
        return;

    toggle (track, property);
}

//==============================================================================
// Knobs

function encoderHandler (encoder)
{
    return function (value)
    {
        // Inc/Dec 2: two's complement, with acceleration - right 1..8, left 127..120.
        var delta = value < 64 ? value : value - 128;

        if (delta != 0)
            runEncoder (ENCODER_ACTIONS[encoder], delta);
    };
}

function steps (delta)
{
    return Math.min (Math.abs (delta), MAX_VIEW_STEPS);
}

function runEncoder (action, delta)
{
    var appView = new LiveAPI ("live_app view");
    var i;

    switch (action)
    {
        // Like the arrow keys - and like Shift with them while Select is held.
        case "cursor":
            for (i = 0; i < steps (delta); ++i)
                appView.call ("scroll_view", delta > 0 ? 3 : 2, "Arranger", selectHeld ? 1 : 0);
            break;

        case "zoom":
            for (i = 0; i < steps (delta); ++i)
                appView.call ("zoom_view", delta > 0 ? ZOOM_IN : ZOOM_OUT, "Arranger", 0);
            break;

        // Live's API cannot scroll a view without moving the selection.
        case "sideScroll":
            outlet (1, "hscroll", SIDE_SCROLL_SIGN * delta * SIDE_SCROLL_LINES);
            break;

        case "volume":       nudge ("live_set view selected_track mixer_device volume", delta); break;
        case "pan":          nudge ("live_set view selected_track mixer_device panning", delta); break;
        case "send1":        nudge ("live_set view selected_track mixer_device sends 0", delta); break;
        case "cueVolume":    nudge ("live_set master_track mixer_device cue_volume", delta); break;
        case "masterVolume": nudge ("live_set master_track mixer_device volume", delta); break;
    }
}

function nudge (path, delta)
{
    var parameter = new LiveAPI (path);

    if (parameter.id == 0)
        return;

    var low = Number (parameter.get ("min"));
    var high = Number (parameter.get ("max"));
    var value = Number (parameter.get ("value")) + delta * PARAM_STEP * (high - low);

    parameter.set ("value", Math.max (low, Math.min (high, value)));
}

//==============================================================================
// Pad colours

// From the device's menus: "colour <pad> <code>", "pressed <code>".
function colour (pad, code)
{
    if (pad >= 1 && pad <= 16)
    {
        padColours[pad - 1] = code;
        coloursTask.cancel ();
        coloursTask.schedule (30);     // a preset recall sets all sixteen at once
    }
}

function pressed (code)
{
    pressedColour = code;
    coloursTask.cancel ();
    coloursTask.schedule (30);
}

var coloursTask = new Task (function () { sendColours (); });

function sendColours ()
{
    if (surface == null)
        return;

    var held = [];

    for (var i = 0; i < 16; ++i)
        held.push (pressedColour);

    sendColourBlock (COLOUR_ADDRESS_OFF, padColours);
    sendColourBlock (COLOUR_ADDRESS_ON, held);
}

// F0 47 00 24 31 00 13 10 <address: two 7-bit bytes> <16 colours> F7 - a write into the loaded preset.
function sendColourBlock (address, colours)
{
    var message = ["send_midi", 0xf0, 0x47, 0x00, 0x24, 0x31, 0x00, 0x13, 0x10,
                   (address >> 7) & 0x7f, address & 0x7f];

    for (var i = 0; i < 16; ++i)
        message.push (Math.max (0, Math.min (16, Math.floor (colours[i]))));

    message.push (0xf7);
    surface.call.apply (surface, message);
}
