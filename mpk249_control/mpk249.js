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

    Pads are Akai's numbering: 1 bottom left, 13 top left. Each pad has a
    colour, and the pads that show a state - a track pad its track selected,
    the metronome, mute, solo and arm pads theirs on - a second, "lit" colour.

    Max's js is an old JavaScript: no let, const or arrow functions.
*/

autowatch = 1;
inlets = 1;
outlets = 3;        // 0: the status line   1: requests for mpk249-keys.js   2: the Step menu

var SURFACE_TYPE = "MPK249_Flow";

//==============================================================================
// What each control does - the place to change things.

var PAD_ACTIONS = {
    // Top two rows: select tracks 1-8, reading order. Lit: the selected track.
    13: ["track", 1], 14: ["track", 2], 15: ["track", 3], 16: ["track", 4],
     9: ["track", 5], 10: ["track", 6], 11: ["track", 7], 12: ["track", 8],

    // Third row.
    5: ["pluginWindow"],    // Cmd-Alt-P: show/hide the plug-in windows
    6: ["select"],          // held: the cursor knob extends the time selection
    7: ["gridCoarser"],     // Cmd-2: widen the grid
    8: ["gridFiner"],       // Cmd-1: narrow the grid

    // Bottom row: the metronome, and the selected track's. Lit: on.
    1: ["metronome"],
    2: ["mute"],
    3: ["solo"],
    4: ["arm"]
};

var ENCODER_ACTIONS = {
    1: "cursor",            // the insert marker (or start marker - the device's Cursor menu); Select held: the time selection
    2: "sideScroll",        // the arrangement, sideways
    3: "zoom",              // the arrangement, horizontally
    4: "volume",            // selected track
    5: "pan",               // selected track
    6: "send1",             // selected track
    7: "cueVolume",
    8: "masterVolume"
};

// The view knobs act once per this many detents, however fast they turn (the device's numboxes).
var detentsPerStep = { cursor: 2, sideScroll: 1, zoom: 2 };

/*  What the cursor knob moves (the device's Cursor menu). Live's API can
    nudge the insert marker by the grid (scroll_view, the arrows) but not read
    or place it, and can place the start marker (current_song_time) but knows
    nothing of the grid. So:

    0  Both: each in its own way, by the same distance - the insert marker a
       grid step, the start marker by Step. Together as long as Step is the
       grid: the grid pads move Step with the grid (halving or doubling it),
       which holds for a fixed grid. One click in the arrangement lines the
       two markers up. The default; types nothing.
    1  Arrows: the arrow keys, typed (mpk249-keys.js) - Live moves both, by
       its own grid. Only into Live's main window, never a plug-in's.
    2  Start: the start marker alone, by Step.

    With Select held: Shift and the arrows, growing the time selection.
    With the loop brace selected, the arrows move the loop - Live's doing.
*/
var cursorMode = 0;
var CURSOR_STEPS = [0.125, 0.25, 0.5, 1, 2, 4, 8, 16, 32];   // the device's Step menu, in beats
var cursorStepIndex = 1;
var cursorStep = CURSOR_STEPS[cursorStepIndex];

var PARAM_STEP = 0.005;         // of a parameter's range, per knob step (mixer knobs keep their acceleration)
/*  The side scroll is a mouse scroll at the pointer: in lines or pixels, not
    bars - how far a bar is on screen depends on the zoom, which Live's API
    does not tell. The device's Scroll menu picks the kind of event (Live
    ignored plain horizontal lines) and its Amount the distance per step, to
    be set so a step is a bar at the zoom in use.
*/
var SCROLL_STYLES = ["pixel", "shift", "line"];     // the device's Scroll menu
var scrollStyle = "pixel";
var scrollAmount = 40;
var SIDE_SCROLL_SIGN = -1;      // flip if turning right scrolls left
var ZOOM_IN = 3, ZOOM_OUT = 2;  // zoom_view directions; swap if backwards

// Bank A's pad colours in the MPK's memory, Akai pad order: unpressed, pressed.
var COLOUR_ADDRESS_OFF = 0x57c;
var COLOUR_ADDRESS_ON = 0x5bc;

//==============================================================================

var surface = null;
var observers = [];
var selectHeld = false;

// Set by the device's menus (colour codes 0-16, as the MPK's manual lists them; 0 is off).
var padColours = [16, 16, 16, 16, 4, 15, 7, 15, 16, 16, 16, 16, 16, 16, 16, 16];
var litColours = [4, 2, 8, 1, 0, 0, 0, 0, 5, 5, 5, 5, 5, 5, 5, 5];
var pressedColour = 16;

var lastSent = {};          // address -> the block last written there

// Kept from Live's own notifications, so lighting a pad asks Live nothing:
// every LiveAPI call is a round trip between Max and Live.
var selectedTrackId = 0;
var trackIds = [];
var masterId = 0;
var metronomeOn = false;
var trackState = { mute: false, solo: false, arm: false };
var trackObservers = {};    // mute/solo/arm -> an observer moved to each selected track

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
            ids.push (Number (list[i + 1]));

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
    trackObservers = {};
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
        status ("No MPK249_Flow control surface. Set it in Preferences > Link/Tempo/MIDI: input MPK249 (Port A), output MPK249 (Remote).");
        return;
    }

    var ok = 0;

    for (var p = 1; p <= 16; ++p)
        ok += watch ("Pad_" + p, padHandler (p)) ? 1 : 0;

    for (var e = 1; e <= 8; ++e)
        ok += watch ("Encoder_" + e, encoderHandler (e)) ? 1 : 0;

    // The transport's Loop button: Cmd-L, loop the selection - not the factory loop on/off.
    ok += watch ("Loop", function (value) { if (value > 0) outlet (1, "key", "loopSelection"); }) ? 1 : 0;

    status ("MPK249: " + ok + " of 25 controls.");

    lastSent = {};
    nudged = {};
    appViewApi = null;
    songApi = null;
    masterId = Number (new LiveAPI ("live_set master_track").id);

    // What the lit pads show: the selected track (and its mute, solo, arm), the metronome.
    for (var name in trackState)
        trackObservers[name] = trackStateObserver (name);

    observeLive ("live_set", "visible_tracks", function (args) { trackIds = idsOf (args); });
    observeLive ("live_set", "metronome", function (args) { metronomeOn = Number (args[0]) != 0; });
    observeLive ("live_set view", "selected_track", function (args)
    {
        var ids = idsOf (args);
        selectedTrackId = ids.length ? ids[0] : 0;
        followSelectedTrack ();
    });

    sendColours ();
}

// Calls keep (values) with what a property holds now and each time it changes, then relights.
function observeLive (path, property, keep)
{
    var observer = new LiveAPI (function (args)
    {
        if (args[0] != property)
            return;

        keep (args.slice (1));
        sendColours ();     // unchanged blocks are not resent
    }, path);

    observer.property = property;
    observers.push (observer);
}

function trackStateObserver (name)
{
    var observer = new LiveAPI (function (args)
    {
        if (args[0] != name)
            return;

        trackState[name] = Number (args[1]) != 0;
        sendColours ();
    }, "live_set");     // somewhere to start; followSelectedTrack moves it

    observers.push (observer);
    return observer;
}

/*  Points the mute/solo/arm observers at the newly selected track. The master
    has none of the three, a return track or a group no arm: asking a track for
    a property it lacks is an error, so those are simply not lit.
*/
function followSelectedTrack ()
{
    var isMaster = selectedTrackId == 0 || selectedTrackId == masterId;
    var canArm = ! isMaster && Number (new LiveAPI ("id " + selectedTrackId).get ("can_be_armed")) != 0;

    for (var name in trackObservers)
    {
        var observer = trackObservers[name];
        var applies = ! isMaster && (name != "arm" || canArm);

        observer.property = "";
        trackState[name] = false;

        if (applies)
        {
            observer.id = selectedTrackId;
            observer.property = name;   // reports the value it has now, too
        }
    }
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
        case "gridCoarser":     outlet (1, "key", "gridCoarser"); followGrid (1); break;
        case "gridFiner":       outlet (1, "key", "gridFiner"); followGrid (-1); break;
        case "metronome":       toggle (song (), "metronome"); break;
        case "mute":            toggleOnTrack ("mute"); break;
        case "solo":            toggleOnTrack ("solo"); break;
        case "arm":             toggleOnTrack ("arm"); break;
    }
}

function selectTrack (number)
{
    if (number > trackIds.length)
        return;

    var from = trackIds.indexOf (selectedTrackId);
    var to = number - 1;
    var target = trackIds[to];

    // Lit first: Live's own notice of the change comes a round trip later.
    selectedTrackId = target;
    sendColours ();

    /*  Down or up the arrangement a track at a time, as the arrow keys do: that
        takes the insert marker to the track at the same time position, which
        setting the selected track does not. Only with the arrangement shown.
    */
    if (from >= 0 && from != to && Number (appView ().call ("is_view_visible", "Arranger")))
        for (var i = 0; i < Math.abs (to - from); ++i)
            appView ().call ("scroll_view", to > from ? 1 : 0, "Arranger", 0);

    var view = new LiveAPI ("live_set view");

    if (idsOf (view.get ("selected_track"))[0] != target)
        view.set ("selected_track", "id", target);
}

function toggle (api, property)
{
    api.set (property, Number (api.get (property)) ? 0 : 1);
}

function toggleOnTrack (property)
{
    // The observers know what applies to the selected track; one is pointed there only if it does.
    var observer = trackObservers[property];

    if (observer == null || observer.property != property)
        return;

    toggle (new LiveAPI ("id " + selectedTrackId), property);
}

//==============================================================================
// Knobs

var accumulated = {};       // view knob -> detents turned toward its next step

function encoderHandler (encoder)
{
    return function (value)
    {
        // Inc/Dec 2: two's complement, with acceleration - right 1..8, left 127..120.
        var delta = value < 64 ? value : value - 128;
        var action = ENCODER_ACTIONS[encoder];

        outlet (1, "log", "knob " + encoder + " (" + action + ") " + delta);

        if (delta == 0)
            return;

        if (detentsPerStep[action] == null)
        {
            runEncoder (action, delta);
            return;
        }

        // A view knob counts detents, not speed: one message is one detent.
        var direction = delta > 0 ? 1 : -1;
        var sofar = accumulated[action] || 0;

        if (sofar * direction < 0)
            sofar = 0;              // turned back: start over

        sofar += direction;

        if (Math.abs (sofar) >= Math.max (1, detentsPerStep[action]))
        {
            sofar = 0;
            runEncoder (action, direction);
        }

        accumulated[action] = sofar;
    };
}

var appViewApi = null;
var songApi = null;

function appView ()
{
    if (appViewApi == null)
        appViewApi = new LiveAPI ("live_app view");

    return appViewApi;
}

function song ()
{
    if (songApi == null)
        songApi = new LiveAPI ("live_set");

    return songApi;
}

function runEncoder (action, delta)
{
    switch (action)
    {
        case "cursor":
            if (selectHeld)
            {
                if (cursorMode == 1)
                    typeArrow (delta > 0, true);
                else
                    appView ().call ("scroll_view", delta > 0 ? 3 : 2, "Arranger", 1);
            }
            else if (cursorMode == 0)
            {
                appView ().call ("scroll_view", delta > 0 ? 3 : 2, "Arranger", 0);
                moveStartMarker (delta);
            }
            else if (cursorMode == 1)
            {
                typeArrow (delta > 0, false);
            }
            else
            {
                moveStartMarker (delta);
            }
            break;

        case "zoom":
            appView ().call ("zoom_view", delta > 0 ? ZOOM_IN : ZOOM_OUT, "Arranger", 0);
            break;

        // Live's API cannot scroll a view without moving the selection.
        case "sideScroll":
            outlet (1, "hscroll", SIDE_SCROLL_SIGN * delta * scrollAmount, scrollStyle);
            break;

        case "volume":       nudge ("live_set view selected_track mixer_device volume", delta); break;
        case "pan":          nudge ("live_set view selected_track mixer_device panning", delta); break;
        case "send1":        nudge ("live_set view selected_track mixer_device sends 0", delta); break;
        case "cueVolume":    nudge ("live_set master_track mixer_device cue_volume", delta); break;
        case "masterVolume": nudge ("live_set master_track mixer_device volume", delta); break;
    }
}

/*  An arrow key, typed - into the arrangement, which is given the keyboard
    first (at most once a second: it is a round trip to Live) so the key
    does not land in the browser or a clip.
*/
var arrangerFocusedAt = 0;

function typeArrow (right, shift)
{
    var now = new Date ().getTime ();

    if (now - arrangerFocusedAt > 1000)
    {
        appView ().call ("focus_view", "Arranger");
        arrangerFocusedAt = now;
    }

    outlet (1, "key", (shift ? "shift" : "") + (right ? (shift ? "Right" : "right") : (shift ? "Left" : "left")));
}

/*  The start marker, set directly - not with scroll_view, which is the arrow
    keys: with the loop brace selected those move the loop instead.
*/
function moveStartMarker (direction)
{
    var now = Number (song ().get ("current_song_time"));
    var next = Math.round ((now + direction * cursorStep) / cursorStep) * cursorStep;

    song ().set ("current_song_time", Math.max (0, next));
}

/*  The parameter at each path, kept with its range: a knob tick is then one
    read and one write. A path through the selected track is looked up again
    when the selection has changed since.
*/
var nudged = {};

function nudge (path, delta)
{
    var entry = nudged[path];

    if (entry == null || entry.track != selectedTrackId)
    {
        var api = new LiveAPI (path);

        if (api.id == 0)
            return;

        entry = nudged[path] = { api: api, track: selectedTrackId,
                                 low: Number (api.get ("min")), high: Number (api.get ("max")) };
    }

    var value = Number (entry.api.get ("value")) + delta * PARAM_STEP * (entry.high - entry.low);
    entry.api.set ("value", Math.max (entry.low, Math.min (entry.high, value)));
}

//==============================================================================
// From the device's controls

// "detents cursor|sideScroll|zoom <n>"
function detents (name, n)
{
    if (detentsPerStep[name] != null)
    {
        detentsPerStep[name] = Math.max (1, Math.floor (n));
        accumulated[name] = 0;
    }
}

// "scrollstyle <menu index>", "scrollamount <n>"
function scrollstyle (index)
{
    if (index >= 0 && index < SCROLL_STYLES.length)
        scrollStyle = SCROLL_STYLES[index];
}

function scrollamount (n)
{
    scrollAmount = Math.max (1, Math.floor (n));
}

// "cursormode <menu index>": 0 both, 1 arrows, 2 start
function cursormode (index)
{
    cursorMode = index >= 0 && index <= 2 ? index : 0;
}

// "cursorstep <menu index>"
function cursorstep (index)
{
    if (index >= 0 && index < CURSOR_STEPS.length)
    {
        cursorStepIndex = index;
        cursorStep = CURSOR_STEPS[index];
    }
}

// A grid pad halves or doubles Live's grid: Step does the same, shown in its menu.
function followGrid (direction)
{
    var index = Math.max (0, Math.min (CURSOR_STEPS.length - 1, cursorStepIndex + direction));

    cursorstep (index);
    outlet (2, index);
}

// "colour <pad> <code>", "lit <pad> <code>", "pressed <code>"
function colour (pad, code)
{
    if (pad >= 1 && pad <= 16)
    {
        padColours[pad - 1] = code;
        scheduleColours ();
    }
}

function lit (pad, code)
{
    if (pad >= 1 && pad <= 16)
    {
        litColours[pad - 1] = code;
        scheduleColours ();
    }
}

function pressed (code)
{
    pressedColour = code;
    scheduleColours ();
}

//==============================================================================
// Pad colours

// Batched: a preset recall sets every menu at once.
var coloursTask = new Task (function () { sendColours (); });

function scheduleColours ()
{
    coloursTask.cancel ();
    coloursTask.schedule (30);
}

function isLit (pad)
{
    var action = PAD_ACTIONS[pad];

    if (action == null)
        return false;

    switch (action[0])
    {
        case "track":       return action[1] <= trackIds.length && trackIds[action[1] - 1] == selectedTrackId;
        case "metronome":   return metronomeOn;
        case "mute":
        case "solo":
        case "arm":         return trackState[action[0]];
    }

    return false;
}

function sendColours ()
{
    if (surface == null)
        return;

    var unpressed = [];
    var held = [];

    for (var pad = 1; pad <= 16; ++pad)
    {
        unpressed.push (isLit (pad) ? litColours[pad - 1] : padColours[pad - 1]);
        held.push (pressedColour);
    }

    sendColourBlock (COLOUR_ADDRESS_OFF, unpressed);
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

    // Only what changed: every track selection would otherwise rewrite both blocks.
    var key = String (address);
    var text = message.join (" ");

    if (lastSent[key] == text)
        return;

    lastSent[key] = text;
    surface.call.apply (surface, message);
}
