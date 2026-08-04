/* ---------------------------------------------------------------------------
   LEVEL-UP VALIDATOR

   You do not need to understand this. Copy the whole file, paste it into the
   "Run script" step of your Airtable automation, and set up the two input
   variables described in SETUP.md step 5.

   What it does, every time someone scans a card and submits the form:

     1. Is this card code real?                  no -> reject
     2. Has this card already been used?         yes -> reject
     3. Is this email a registered member?       no -> reject
     4. Are they exactly one level below it?     no -> reject

   If all four pass, it promotes the member and burns the card so it can never
   be used again. If any fail, it writes the reason to the log and changes
   nothing else.
--------------------------------------------------------------------------- */


// --- Names of your tables and fields -----------------------------------------
// If you named anything differently in Airtable, change it here to match.

const MEMBERS_TABLE = "Members";
const MEMBER_EMAIL = "Email";
const MEMBER_NAME = "Name";
const MEMBER_LEVEL = "Level";
const MEMBER_LAST_ACTIVATED = "Last activated";

const CARDS_TABLE = "Cards";
const CARD_CODE = "Card code";
const CARD_LEVEL = "Level";
const CARD_STATUS = "Status";
const CARD_MEMBER = "Member";
const CARD_ACTIVATED_AT = "Activated at";

const LOG_TABLE = "Activation log";
const LOG_RESULT = "Result";
const LOG_REASON = "Reason";

// -----------------------------------------------------------------------------


const config = input.config();
const submittedCode = (config.code || "").trim().toUpperCase();
const submittedEmail = (config.email || "").trim().toLowerCase();

const members = base.getTable(MEMBERS_TABLE);
const cards = base.getTable(CARDS_TABLE);
const log = base.getTable(LOG_TABLE);

// Everything this script decides ends up in one of these two variables, so
// there is exactly one place where the log gets written at the end.
let result = "rejected";
let reason = "";


// Airtable has no "find one record" call, so we pull the columns we need and
// match in memory. Fine at this scale — a few thousand cards at most.
const cardRows = await cards.selectRecordsAsync({
    fields: [CARD_CODE, CARD_LEVEL, CARD_STATUS],
});
const card = cardRows.records.find(
    r => (r.getCellValueAsString(CARD_CODE) || "").trim().toUpperCase() === submittedCode
);

const memberRows = await members.selectRecordsAsync({
    fields: [MEMBER_EMAIL, MEMBER_NAME, MEMBER_LEVEL],
});
const member = memberRows.records.find(
    r => (r.getCellValueAsString(MEMBER_EMAIL) || "").trim().toLowerCase() === submittedEmail
);


if (!card) {
    reason = "No such card code";

} else if (card.getCellValueAsString(CARD_STATUS) === "activated") {
    reason = "Card already activated";

} else if (card.getCellValueAsString(CARD_STATUS) === "void") {
    reason = "Card has been voided";

} else if (!member) {
    reason = "No member with that email — they need to sign up first";

} else {
    const cardLevel = card.getCellValue(CARD_LEVEL);
    const memberLevel = member.getCellValue(MEMBER_LEVEL) || 0;

    if (memberLevel >= cardLevel) {
        reason = `Already level ${memberLevel} — this is a level ${cardLevel} card`;
    } else if (memberLevel !== cardLevel - 1) {
        reason = `Cannot skip levels — they are level ${memberLevel}, this card is level ${cardLevel}`;
    } else {
        // All four checks passed. Burn the card, promote the member.
        const now = new Date().toISOString();

        await cards.updateRecordAsync(card.id, {
            [CARD_STATUS]: { name: "activated" },
            [CARD_MEMBER]: [{ id: member.id }],
            [CARD_ACTIVATED_AT]: now,
        });

        await members.updateRecordAsync(member.id, {
            [MEMBER_LEVEL]: cardLevel,
            [MEMBER_LAST_ACTIVATED]: now,
        });

        result = "activated";
        reason = `Promoted to level ${cardLevel}`;
    }
}


await log.updateRecordAsync(config.logRecordId, {
    [LOG_RESULT]: { name: result },
    [LOG_REASON]: reason,
});

// Passed to the next automation step, so it can send the right email and show
// the right screen — the celebratory one, or the "ask a member of staff" one.
output.set("result", result);
output.set("reason", reason);
output.set("memberName", member ? member.getCellValueAsString(MEMBER_NAME) : "");
output.set("level", result === "activated" ? card.getCellValue(CARD_LEVEL) : "");
