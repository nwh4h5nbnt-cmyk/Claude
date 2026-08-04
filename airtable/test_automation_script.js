/* ---------------------------------------------------------------------------
   Tests for automation_script.js

   Airtable has no local test runner, so this file fakes just enough of its API
   (base, input, output) to run the real script unmodified and check that every
   accept/reject path behaves.

   Run with:  node airtable/test_automation_script.js

   This exists so that a change to the validator can be checked before it goes
   anywhere near real member data.
--------------------------------------------------------------------------- */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SCRIPT = fs.readFileSync(path.join(__dirname, "automation_script.js"), "utf8");


// --- Fake Airtable -----------------------------------------------------------

function makeRecord(id, fields) {
    return {
        id,
        fields,
        getCellValue: f => fields[f],
        getCellValueAsString: f => {
            const v = fields[f];
            if (v === null || v === undefined) return "";
            return typeof v === "object" ? (v.name ?? String(v)) : String(v);
        },
    };
}

function makeBase(state) {
    const writes = [];
    const table = (name, records) => ({
        selectRecordsAsync: async () => ({ records }),
        updateRecordAsync: async (id, changes) => {
            writes.push({ table: name, id, changes });
            const rec = records.find(r => r.id === id);
            if (rec) Object.assign(rec.fields, changes);
        },
    });
    return {
        base: {
            getTable: name => {
                if (name === "Members") return table("Members", state.members);
                if (name === "Cards") return table("Cards", state.cards);
                if (name === "Activation log") return table("Activation log", state.log);
                throw new Error(`unknown table ${name}`);
            },
        },
        writes,
    };
}

async function run(state, config) {
    const { base, writes } = makeBase(state);
    const out = {};
    const ctx = {
        base,
        input: { config: () => config },
        output: { set: (k, v) => { out[k] = v; } },
        console,
    };
    // The script is written as top-level code with awaits, which is exactly how
    // Airtable executes it. Wrapping in an async IIFE reproduces that.
    await vm.runInNewContext(`(async () => { ${SCRIPT} })()`, ctx);
    return { out, writes };
}


// --- Fixtures ----------------------------------------------------------------

function freshState() {
    return {
        members: [
            makeRecord("mem1", { Email: "sam@example.com", Name: "Sam", Level: 2 }),
            makeRecord("mem2", { Email: "alex@example.com", Name: "Alex", Level: 0 }),
        ],
        cards: [
            makeRecord("c_l1", { "Card code": "AAA111", Level: 1, Status: "unissued" }),
            makeRecord("c_l3", { "Card code": "B9V4LR", Level: 3, Status: "unissued" }),
            makeRecord("c_l4", { "Card code": "CCC333", Level: 4, Status: "unissued" }),
            makeRecord("c_used", { "Card code": "DDD444", Level: 3, Status: "activated" }),
            makeRecord("c_void", { "Card code": "EEE555", Level: 3, Status: "void" }),
        ],
        log: [makeRecord("log1", {})],
    };
}

const base_cfg = { logRecordId: "log1" };


// --- Tests -------------------------------------------------------------------

const tests = [];
const test = (name, fn) => tests.push({ name, fn });

function assert(cond, msg) {
    if (!cond) throw new Error(msg);
}

test("happy path: level 2 member scans a level 3 card", async () => {
    const state = freshState();
    const { out, writes } = await run(state, {
        ...base_cfg, code: "B9V4LR", email: "sam@example.com",
    });
    assert(out.result === "activated", `expected activated, got ${out.result}`);
    assert(out.level === 3, `expected level 3, got ${out.level}`);
    assert(out.memberName === "Sam", `expected Sam, got ${out.memberName}`);

    const card = state.cards.find(c => c.id === "c_l3");
    assert(card.fields.Status.name === "activated", "card should be burned");
    assert(card.fields.Member[0].id === "mem1", "card should link to the member");
    assert(card.fields["Activated at"], "card should be timestamped");

    const member = state.members.find(m => m.id === "mem1");
    assert(member.fields.Level === 3, `member should be level 3, got ${member.fields.Level}`);
});

test("unranked member scans their level 1 card", async () => {
    const state = freshState();
    const { out } = await run(state, {
        ...base_cfg, code: "AAA111", email: "alex@example.com",
    });
    assert(out.result === "activated", `expected activated, got ${out.result}`);
    assert(state.members.find(m => m.id === "mem2").fields.Level === 1, "should be level 1");
});

test("rejects a made-up code", async () => {
    const state = freshState();
    const { out } = await run(state, {
        ...base_cfg, code: "NOTREAL", email: "sam@example.com",
    });
    assert(out.result === "rejected", "should reject");
    assert(/No such card/.test(out.reason), out.reason);
});

test("rejects a card that has already been activated", async () => {
    const state = freshState();
    const { out } = await run(state, {
        ...base_cfg, code: "DDD444", email: "sam@example.com",
    });
    assert(out.result === "rejected", "should reject");
    assert(/already activated/.test(out.reason), out.reason);
});

test("rejects a voided card", async () => {
    const state = freshState();
    const { out } = await run(state, {
        ...base_cfg, code: "EEE555", email: "sam@example.com",
    });
    assert(out.result === "rejected", "should reject");
    assert(/voided/.test(out.reason), out.reason);
});

test("rejects an unknown email", async () => {
    const state = freshState();
    const { out } = await run(state, {
        ...base_cfg, code: "B9V4LR", email: "nobody@example.com",
    });
    assert(out.result === "rejected", "should reject");
    assert(/sign up first/.test(out.reason), out.reason);
});

test("blocks level skipping: level 2 member scans a level 4 card", async () => {
    const state = freshState();
    const { out } = await run(state, {
        ...base_cfg, code: "CCC333", email: "sam@example.com",
    });
    assert(out.result === "rejected", "should reject");
    assert(/Cannot skip/.test(out.reason), out.reason);
    assert(state.members.find(m => m.id === "mem1").fields.Level === 2, "level must not change");
    assert(state.cards.find(c => c.id === "c_l4").fields.Status === "unissued",
        "rejected card must stay spendable");
});

test("rejects re-scanning a level they already hold", async () => {
    const state = freshState();
    state.members[0].fields.Level = 3;
    const { out } = await run(state, {
        ...base_cfg, code: "B9V4LR", email: "sam@example.com",
    });
    assert(out.result === "rejected", "should reject");
    assert(/Already level 3/.test(out.reason), out.reason);
});

test("a rejected scan leaves the card usable by the right person", async () => {
    const state = freshState();
    await run(state, { ...base_cfg, code: "B9V4LR", email: "nobody@example.com" });
    const { out } = await run(state, {
        ...base_cfg, code: "B9V4LR", email: "sam@example.com",
    });
    assert(out.result === "activated", "the legitimate member should still be able to use it");
});

test("the same card cannot promote two people", async () => {
    const state = freshState();
    await run(state, { ...base_cfg, code: "B9V4LR", email: "sam@example.com" });
    state.members.push(makeRecord("mem3", {
        Email: "jo@example.com", Name: "Jo", Level: 2,
    }));
    const { out } = await run(state, {
        ...base_cfg, code: "B9V4LR", email: "jo@example.com",
    });
    assert(out.result === "rejected", "second use must fail");
    assert(state.members.find(m => m.id === "mem3").fields.Level === 2, "Jo must not be promoted");
});

test("tolerates messy input: whitespace and wrong case", async () => {
    const state = freshState();
    const { out } = await run(state, {
        ...base_cfg, code: "  b9v4lr ", email: " SAM@Example.COM  ",
    });
    assert(out.result === "activated", `expected activated, got ${out.result}: ${out.reason}`);
});

test("always writes a log line, even on rejection", async () => {
    const state = freshState();
    const { writes } = await run(state, {
        ...base_cfg, code: "NOTREAL", email: "sam@example.com",
    });
    const logWrites = writes.filter(w => w.table === "Activation log");
    assert(logWrites.length === 1, `expected 1 log write, got ${logWrites.length}`);
    assert(logWrites[0].changes.Result.name === "rejected", "log should record the rejection");
});

test("a rejection writes nothing except the log", async () => {
    const state = freshState();
    const { writes } = await run(state, {
        ...base_cfg, code: "CCC333", email: "sam@example.com",
    });
    const touched = writes.filter(w => w.table !== "Activation log");
    assert(touched.length === 0, `rejection touched ${touched.length} other records`);
});


// --- Runner ------------------------------------------------------------------

(async () => {
    let passed = 0, failed = 0;
    for (const t of tests) {
        try {
            await t.fn();
            console.log(`  PASS  ${t.name}`);
            passed++;
        } catch (err) {
            console.log(`  FAIL  ${t.name}\n          ${err.message}`);
            failed++;
        }
    }
    console.log(`\n${passed} passed, ${failed} failed`);
    process.exit(failed ? 1 : 0);
})();
