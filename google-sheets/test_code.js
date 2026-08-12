/* ---------------------------------------------------------------------------
   Tests for Code.gs

   Apps Script has no local test runner, so this file fakes just enough of
   Google's API (SpreadsheetApp, LockService) to run the real Code.gs
   unmodified and check that every accept/reject path behaves.

   Run with:  node google-sheets/test_code.js

   This exists so that a change to the validator can be checked before it goes
   anywhere near real member data.
--------------------------------------------------------------------------- */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SCRIPT = fs.readFileSync(path.join(__dirname, "Code.gs"), "utf8");


// --- Fake Google Sheets ------------------------------------------------------

function makeSheet(name, grid) {
    return {
        _name: name,
        _grid: grid,
        getName: () => name,
        getDataRange: () => ({ getValues: () => grid.map(r => r.slice()) }),
        getRange: (row, col) => ({
            setValue: v => {
                while (grid.length < row) grid.push(new Array(grid[0].length).fill(""));
                grid[row - 1][col - 1] = v;
            },
        }),
        appendRow: arr => { grid.push(arr.slice()); },
    };
}

function makeContext(tabs) {
    const sheets = {};
    for (const [name, grid] of Object.entries(tabs)) sheets[name] = makeSheet(name, grid);

    return {
        sheets,
        ctx: {
            SpreadsheetApp: {
                getActive: () => ({ getSheetByName: n => sheets[n] || null }),
            },
            LockService: {
                getScriptLock: () => ({ waitLock: () => {}, releaseLock: () => {} }),
            },
            console,
            Array,
            Date,
            Number,
            String,
            Error,
        },
    };
}

function load(tabs) {
    const { sheets, ctx } = makeContext(tabs);
    vm.runInNewContext(SCRIPT, ctx);
    return { api: ctx, sheets };
}


// --- Fixtures ----------------------------------------------------------------

function freshTabs(opts) {
    opts = opts || {};
    // Deliberately non-obvious column order in Cards, to prove the script
    // finds columns by header name rather than position.
    const cards = opts.shuffledCards
        ? [
            ["Batch", "Status", "Card code", "Activated at", "Level", "Member email"],
            ["b", "unissued", "AAA111", "", 1, ""],
            ["b", "unissued", "B9V4LR", "", 3, ""],
            ["b", "unissued", "CCC333", "", 4, ""],
            ["b", "activated", "DDD444", "", 3, "old@example.com"],
            ["b", "void", "EEE555", "", 3, ""],
        ]
        : [
            ["Card code", "Level", "Status", "Member email", "Activated at", "Batch"],
            ["AAA111", 1, "unissued", "", "", "b"],
            ["B9V4LR", 3, "unissued", "", "", "b"],
            ["CCC333", 4, "unissued", "", "", "b"],
            ["DDD444", 3, "activated", "old@example.com", "", "b"],
            ["EEE555", 3, "void", "", "", "b"],
        ];

    return {
        "Members": [
            ["Email", "Name", "Level", "Joined", "Last activated", "Consent"],
            ["sam@example.com", "Sam", 2, "", "", true],
            ["alex@example.com", "Alex", 0, "", "", true],
        ],
        "Cards": cards,
        "Activation log": [["Time", "Submitted code", "Submitted email", "Result", "Reason"]],
        "Signup responses": [["Timestamp", "Name", "Email", "Consent"]],
        "Activation responses": [["Timestamp", "Card code", "Confirm your email"]],
    };
}

const cell = (grid, row, header) => grid[row][grid[0].indexOf(header)];
const findMember = (grid, email) => grid.findIndex(r => r[0] === email);
const findCard = (grid, code) => grid.findIndex(r => r[grid[0].indexOf("Card code")] === code);

/** Builds the event object Google hands to onFormSubmit. */
function submitEvent(sheets, tabName, namedValues) {
    return { range: { getSheet: () => sheets[tabName] }, namedValues };
}


// --- Tests -------------------------------------------------------------------

const tests = [];
const test = (name, fn) => tests.push({ name, fn });
const assert = (cond, msg) => { if (!cond) throw new Error(msg); };


test("happy path: level 2 member scans a level 3 card", () => {
    const tabs = freshTabs();
    const { api } = load(tabs);
    const out = api.validate("B9V4LR", "sam@example.com");

    assert(out.result === "activated", `expected activated, got ${out.result}: ${out.reason}`);

    const c = tabs.Cards[findCard(tabs.Cards, "B9V4LR")];
    assert(cell(tabs.Cards, findCard(tabs.Cards, "B9V4LR"), "Status") === "activated",
        "card should be burned");
    assert(cell(tabs.Cards, findCard(tabs.Cards, "B9V4LR"), "Member email") === "sam@example.com",
        "card should record the member");
    assert(c[tabs.Cards[0].indexOf("Activated at")] instanceof Date, "should be timestamped");

    assert(cell(tabs.Members, findMember(tabs.Members, "sam@example.com"), "Level") === 3,
        "member should be level 3");
});

test("works regardless of column order", () => {
    const tabs = freshTabs({ shuffledCards: true });
    const { api } = load(tabs);
    const out = api.validate("B9V4LR", "sam@example.com");
    assert(out.result === "activated", `expected activated, got ${out.reason}`);
    assert(cell(tabs.Cards, findCard(tabs.Cards, "B9V4LR"), "Status") === "activated",
        "card should be burned even with columns rearranged");
});

test("unranked member scans their level 1 card", () => {
    const tabs = freshTabs();
    const { api } = load(tabs);
    const out = api.validate("AAA111", "alex@example.com");
    assert(out.result === "activated", `expected activated, got ${out.reason}`);
    assert(cell(tabs.Members, findMember(tabs.Members, "alex@example.com"), "Level") === 1,
        "should be level 1");
});

test("rejects a made-up code", () => {
    const { api } = load(freshTabs());
    const out = api.validate("NOTREAL", "sam@example.com");
    assert(out.result === "rejected", "should reject");
    assert(/No such card/.test(out.reason), out.reason);
});

test("rejects a card that has already been activated", () => {
    const { api } = load(freshTabs());
    const out = api.validate("DDD444", "sam@example.com");
    assert(out.result === "rejected", "should reject");
    assert(/already activated/.test(out.reason), out.reason);
});

test("rejects a voided card", () => {
    const { api } = load(freshTabs());
    const out = api.validate("EEE555", "sam@example.com");
    assert(out.result === "rejected", "should reject");
    assert(/voided/.test(out.reason), out.reason);
});

test("rejects an unknown email", () => {
    const { api } = load(freshTabs());
    const out = api.validate("B9V4LR", "nobody@example.com");
    assert(out.result === "rejected", "should reject");
    assert(/sign up first/.test(out.reason), out.reason);
});

test("blocks level skipping: level 2 member scans a level 4 card", () => {
    const tabs = freshTabs();
    const { api } = load(tabs);
    const out = api.validate("CCC333", "sam@example.com");

    assert(out.result === "rejected", "should reject");
    assert(/Cannot skip/.test(out.reason), out.reason);
    assert(cell(tabs.Members, findMember(tabs.Members, "sam@example.com"), "Level") === 2,
        "level must not change");
    assert(cell(tabs.Cards, findCard(tabs.Cards, "CCC333"), "Status") === "unissued",
        "rejected card must stay spendable");
});

test("rejects re-scanning a level they already hold", () => {
    const tabs = freshTabs();
    tabs.Members[1][2] = 3;
    const { api } = load(tabs);
    const out = api.validate("B9V4LR", "sam@example.com");
    assert(out.result === "rejected", "should reject");
    assert(/Already level 3/.test(out.reason), out.reason);
});

test("a rejected scan leaves the card usable by the right person", () => {
    const tabs = freshTabs();
    const { api } = load(tabs);
    api.validate("B9V4LR", "nobody@example.com");
    const out = api.validate("B9V4LR", "sam@example.com");
    assert(out.result === "activated", "the legitimate member should still be able to use it");
});

test("the same card cannot promote two people", () => {
    const tabs = freshTabs();
    tabs.Members.push(["jo@example.com", "Jo", 2, "", "", true]);
    const { api } = load(tabs);

    api.validate("B9V4LR", "sam@example.com");
    const out = api.validate("B9V4LR", "jo@example.com");

    assert(out.result === "rejected", "second use must fail");
    assert(cell(tabs.Members, findMember(tabs.Members, "jo@example.com"), "Level") === 2,
        "Jo must not be promoted");
});

test("tolerates messy input: whitespace and wrong case", () => {
    const { api } = load(freshTabs());
    const out = api.validate("  b9v4lr ", " SAM@Example.COM  ");
    assert(out.result === "activated", `expected activated, got ${out.reason}`);
});

test("a rejection changes nothing in Members or Cards", () => {
    const tabs = freshTabs();
    const before = JSON.stringify([tabs.Members, tabs.Cards]);
    const { api } = load(tabs);
    api.validate("CCC333", "sam@example.com");
    assert(JSON.stringify([tabs.Members, tabs.Cards]) === before,
        "rejection must not touch Members or Cards");
});


// --- Form submission paths ---------------------------------------------------

test("activation form writes a log line on success", () => {
    const tabs = freshTabs();
    const { api, sheets } = load(tabs);
    api.onFormSubmit(submitEvent(sheets, "Activation responses", {
        "Card code": ["B9V4LR"], "Confirm your email": ["sam@example.com"],
    }));

    assert(tabs["Activation log"].length === 2, "expected one log row");
    assert(tabs["Activation log"][1][3] === "activated", "log should say activated");
});

test("activation form writes a log line on rejection too", () => {
    const tabs = freshTabs();
    const { api, sheets } = load(tabs);
    api.onFormSubmit(submitEvent(sheets, "Activation responses", {
        "Card code": ["NOTREAL"], "Confirm your email": ["sam@example.com"],
    }));

    assert(tabs["Activation log"].length === 2, "expected one log row");
    assert(tabs["Activation log"][1][3] === "rejected", "log should say rejected");
    assert(/No such card/.test(tabs["Activation log"][1][4]), "log should say why");
});

test("signup form creates a member at level 0", () => {
    const tabs = freshTabs();
    const { api, sheets } = load(tabs);
    api.onFormSubmit(submitEvent(sheets, "Signup responses", {
        "Name": ["Robin"], "Email": ["Robin@Example.com "], "Consent": ["Yes"],
    }));

    const row = findMember(tabs.Members, "robin@example.com");
    assert(row !== -1, "member should exist, with the email lowercased");
    assert(cell(tabs.Members, row, "Level") === 0, "should start at level 0");
    assert(cell(tabs.Members, row, "Name") === "Robin", "name should be stored");
    assert(cell(tabs.Members, row, "Consent") === true, "consent should be recorded");
});

test("signing up twice does not create two members", () => {
    const tabs = freshTabs();
    const { api, sheets } = load(tabs);
    const before = tabs.Members.length;
    api.onFormSubmit(submitEvent(sheets, "Signup responses", {
        "Name": ["Sam"], "Email": ["sam@example.com"], "Consent": ["Yes"],
    }));
    assert(tabs.Members.length === before, "should not add a duplicate row");
    assert(cell(tabs.Members, findMember(tabs.Members, "sam@example.com"), "Level") === 2,
        "existing level must not be reset");
});

test("an unticked consent box is recorded as false", () => {
    const tabs = freshTabs();
    const { api, sheets } = load(tabs);
    api.onFormSubmit(submitEvent(sheets, "Signup responses", {
        "Name": ["Pat"], "Email": ["pat@example.com"], "Consent": [""],
    }));
    assert(cell(tabs.Members, findMember(tabs.Members, "pat@example.com"), "Consent") === false,
        "consent should be false when not ticked");
});

test("a response from an unrelated tab is ignored", () => {
    const tabs = freshTabs();
    tabs["Some other sheet"] = [["a"]];
    const { api, sheets } = load(tabs);
    const before = JSON.stringify([tabs.Members, tabs.Cards, tabs["Activation log"]]);
    api.onFormSubmit(submitEvent(sheets, "Some other sheet", { "Name": ["x"] }));
    assert(JSON.stringify([tabs.Members, tabs.Cards, tabs["Activation log"]]) === before,
        "unrelated submissions must change nothing");
});


// --- What the web app needs back ---------------------------------------------

test("a successful activation returns the level and the member's name", () => {
    const { api } = load(freshTabs());
    const out = api.validate("B9V4LR", "sam@example.com");
    assert(out.level === 3, `expected level 3, got ${out.level}`);
    assert(out.memberName === "Sam", `expected Sam, got ${out.memberName}`);
});

test("a rejection carries no level or name to render", () => {
    const { api } = load(freshTabs());
    const out = api.validate("CCC333", "sam@example.com");
    assert(out.level === undefined, "rejections must not report a level");
    assert(out.memberName === undefined, "rejections must not report a name");
});

test("lookUpCard reports a real unspent card", () => {
    const { api } = load(freshTabs());
    const out = api.lookUpCard("B9V4LR");
    assert(out.found === true, "should be found");
    assert(out.level === 3, `expected level 3, got ${out.level}`);
    assert(out.spent === false, "should not be spent");
});

test("lookUpCard reports a spent card as spent", () => {
    const { api } = load(freshTabs());
    assert(api.lookUpCard("DDD444").spent === true, "activated card should read as spent");
    assert(api.lookUpCard("EEE555").spent === true, "voided card should read as spent");
});

test("lookUpCard reports an unknown code as not found", () => {
    const { api } = load(freshTabs());
    assert(api.lookUpCard("NOTREAL").found === false, "should not be found");
});

test("lookUpCard changes nothing", () => {
    const tabs = freshTabs();
    const before = JSON.stringify([tabs.Members, tabs.Cards, tabs["Activation log"]]);
    const { api } = load(tabs);
    api.lookUpCard("B9V4LR");
    assert(JSON.stringify([tabs.Members, tabs.Cards, tabs["Activation log"]]) === before,
        "a read-only lookup must not write anything");
});


// --- Runner ------------------------------------------------------------------

let passed = 0, failed = 0;
for (const t of tests) {
    try {
        t.fn();
        console.log(`  PASS  ${t.name}`);
        passed++;
    } catch (err) {
        console.log(`  FAIL  ${t.name}\n          ${err.message}`);
        failed++;
    }
}
console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
