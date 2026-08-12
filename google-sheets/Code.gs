/* ---------------------------------------------------------------------------
   LEVEL-UP VALIDATOR — Google Sheets version

   You do not need to understand this. Copy the whole file, paste it into the
   Apps Script editor attached to your spreadsheet, and set up the trigger
   described in SETUP.md step 6.

   It handles both forms:

     Signup form      -> creates a member at level 0 (Unranked)
     Activation form  -> checks the card, then promotes them one rank

   The four checks on every activation:

     1. Is this card code real?                  no -> reject
     2. Has this card already been used?         yes -> reject
     3. Is this email a registered member?       no -> reject
     4. Are they exactly one level below it?     no -> reject

   Pass all four and it promotes the member and burns the card so it can never
   be used again. Fail any and it writes the reason to the log and changes
   nothing else.
--------------------------------------------------------------------------- */


// --- Names of your tabs ------------------------------------------------------
// If you named any tab differently, change it here to match.

const TAB_MEMBERS = 'Members';
const TAB_CARDS = 'Cards';
const TAB_LOG = 'Activation log';
const TAB_SIGNUP_RESPONSES = 'Signup responses';
const TAB_ACTIVATION_RESPONSES = 'Activation responses';


// --- Your form question titles -----------------------------------------------
// These must match the question titles in your Google Forms exactly, including
// capitalisation. If you reword a question, reword it here too.

const Q_NAME = 'Name';
const Q_EMAIL = 'Email';
const Q_CONSENT = 'Consent';
const Q_CARD_CODE = 'Card code';
const Q_CONFIRM_EMAIL = 'Confirm your email';


// --- Column headers ----------------------------------------------------------
// Looked up by name, so it does not matter what order your columns are in.

const COL_MEMBER_EMAIL = 'Email';
const COL_MEMBER_NAME = 'Name';
const COL_MEMBER_LEVEL = 'Level';
const COL_MEMBER_JOINED = 'Joined';
const COL_MEMBER_LAST_ACTIVATED = 'Last activated';
const COL_MEMBER_CONSENT = 'Consent';

const COL_CARD_CODE = 'Card code';
const COL_CARD_LEVEL = 'Level';
const COL_CARD_STATUS = 'Status';
const COL_CARD_MEMBER = 'Member email';
const COL_CARD_ACTIVATED_AT = 'Activated at';

// -----------------------------------------------------------------------------


/**
 * The single entry point. Google calls this whenever either form is submitted;
 * we work out which one from the tab the response landed in.
 */
function onFormSubmit(e) {
  const tab = e.range.getSheet().getName();

  if (tab === TAB_SIGNUP_RESPONSES) {
    handleSignup(e);
  } else if (tab === TAB_ACTIVATION_RESPONSES) {
    handleActivation(e);
  }
  // Anything else is not one of our forms — ignore it.
}


/**
 * Someone filled in the signup form. Create them at level 0.
 */
function handleSignup(e) {
  const answers = e.namedValues;
  const email = firstAnswer(answers, Q_EMAIL).trim().toLowerCase();
  const name = firstAnswer(answers, Q_NAME).trim();
  const consent = firstAnswer(answers, Q_CONSENT).trim() !== '';

  if (!email) return;

  const members = readTable(TAB_MEMBERS);

  // Someone signing up twice should not become two members.
  if (findRow(members, COL_MEMBER_EMAIL, email) !== -1) return;

  const row = new Array(members.header.length).fill('');
  setCell(members, row, COL_MEMBER_EMAIL, email);
  setCell(members, row, COL_MEMBER_NAME, name);
  setCell(members, row, COL_MEMBER_LEVEL, 0);
  setCell(members, row, COL_MEMBER_JOINED, new Date());
  setCell(members, row, COL_MEMBER_CONSENT, consent);
  members.sheet.appendRow(row);
}


/**
 * Someone scanned a card. Validate it, and promote them if it checks out.
 */
function handleActivation(e) {
  const answers = e.namedValues;
  const code = firstAnswer(answers, Q_CARD_CODE).trim().toUpperCase();
  const email = firstAnswer(answers, Q_CONFIRM_EMAIL).trim().toLowerCase();

  // Two people scanning at the same moment must not both succeed, so only one
  // activation runs at a time. Without this, a shared code could slip through.
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
  } catch (err) {
    log(code, email, 'rejected', 'System busy — please try again');
    return;
  }

  try {
    const result = validate(code, email);
    log(code, email, result.result, result.reason);
  } finally {
    lock.releaseLock();
  }
}


/**
 * The actual decision. Separated out so it can be tested on its own, and so
 * callers other than the form handler can use it — the activation web app
 * calls this directly rather than keeping a second copy of the rules.
 *
 * Always returns { result, reason }. On success it also returns `level` and
 * `memberName`, which the web app needs to render the rank screen.
 */
function validate(code, email) {
  const cards = readTable(TAB_CARDS);
  const members = readTable(TAB_MEMBERS);

  const cardRow = findRow(cards, COL_CARD_CODE, code);
  if (cardRow === -1) {
    return { result: 'rejected', reason: 'No such card code' };
  }

  const status = String(getCell(cards, cardRow, COL_CARD_STATUS)).trim().toLowerCase();
  if (status === 'activated') {
    return { result: 'rejected', reason: 'Card already activated' };
  }
  if (status === 'void') {
    return { result: 'rejected', reason: 'Card has been voided' };
  }

  const memberRow = findRow(members, COL_MEMBER_EMAIL, email);
  if (memberRow === -1) {
    return {
      result: 'rejected',
      reason: 'No member with that email — they need to sign up first',
    };
  }

  const cardLevel = Number(getCell(cards, cardRow, COL_CARD_LEVEL));
  const memberLevel = Number(getCell(members, memberRow, COL_MEMBER_LEVEL)) || 0;

  if (memberLevel >= cardLevel) {
    return {
      result: 'rejected',
      reason: 'Already level ' + memberLevel + ' — this is a level ' + cardLevel + ' card',
    };
  }
  if (memberLevel !== cardLevel - 1) {
    return {
      result: 'rejected',
      reason: 'Cannot skip levels — they are level ' + memberLevel +
              ', this card is level ' + cardLevel,
    };
  }

  // All four checks passed. Burn the card, promote the member.
  const now = new Date();
  writeCell(cards, cardRow, COL_CARD_STATUS, 'activated');
  writeCell(cards, cardRow, COL_CARD_MEMBER, email);
  writeCell(cards, cardRow, COL_CARD_ACTIVATED_AT, now);
  writeCell(members, memberRow, COL_MEMBER_LEVEL, cardLevel);
  writeCell(members, memberRow, COL_MEMBER_LAST_ACTIVATED, now);

  return {
    result: 'activated',
    reason: 'Promoted to level ' + cardLevel,
    level: cardLevel,
    memberName: String(getCell(members, memberRow, COL_MEMBER_NAME) || ''),
  };
}


/**
 * What a card is worth before anyone commits to it — used by the web app to
 * render "Activate LVL 4 card" on arrival, before an email has been entered.
 * Read-only: it changes nothing.
 */
function lookUpCard(code) {
  const cards = readTable(TAB_CARDS);
  const row = findRow(cards, COL_CARD_CODE, code);
  if (row === -1) return { found: false };
  return {
    found: true,
    level: Number(getCell(cards, row, COL_CARD_LEVEL)),
    spent: String(getCell(cards, row, COL_CARD_STATUS)).trim().toLowerCase() !== 'unissued',
  };
}


// --- Small helpers -----------------------------------------------------------

/** Reads a tab into memory, remembering where each named column sits. */
function readTable(tabName) {
  const sheet = SpreadsheetApp.getActive().getSheetByName(tabName);
  if (!sheet) throw new Error('No tab named "' + tabName + '"');

  const values = sheet.getDataRange().getValues();
  const header = (values[0] || []).map(function (h) { return String(h).trim(); });

  const index = {};
  header.forEach(function (name, i) { index[name] = i; });

  return { sheet: sheet, header: header, index: index, rows: values.slice(1) };
}

/** Row number of the first row whose column matches, or -1. Case-insensitive. */
function findRow(table, column, value) {
  const col = table.index[column];
  if (col === undefined) throw new Error('No column named "' + column + '"');

  const needle = String(value).trim().toLowerCase();
  for (let i = 0; i < table.rows.length; i++) {
    if (String(table.rows[i][col]).trim().toLowerCase() === needle) return i;
  }
  return -1;
}

function getCell(table, row, column) {
  return table.rows[row][table.index[column]];
}

/** Writes back to the real sheet. +2 because rows are 0-based and row 1 is the header. */
function writeCell(table, row, column, value) {
  const col = table.index[column];
  if (col === undefined) throw new Error('No column named "' + column + '"');
  table.sheet.getRange(row + 2, col + 1).setValue(value);
  table.rows[row][col] = value;
}

function setCell(table, rowArray, column, value) {
  const col = table.index[column];
  if (col === undefined) throw new Error('No column named "' + column + '"');
  rowArray[col] = value;
}

/** Google Forms hands every answer over as an array of one. */
function firstAnswer(namedValues, question) {
  const v = namedValues[question];
  if (!v) return '';
  return Array.isArray(v) ? String(v[0] || '') : String(v);
}

/** Every scan gets a log line, pass or fail. */
function log(code, email, result, reason) {
  const sheet = SpreadsheetApp.getActive().getSheetByName(TAB_LOG);
  sheet.appendRow([new Date(), code, email, result, reason]);
}
