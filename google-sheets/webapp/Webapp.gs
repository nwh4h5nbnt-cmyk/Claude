/* ---------------------------------------------------------------------------
   ACTIVATION WEB APP — server side

   Add this as a SECOND script file alongside Code.gs in the same Apps Script
   project. Do not paste it into Code.gs; keeping them separate means the form
   handler and the web app can be read independently.

   This file deliberately contains no rules. Every decision is made by
   validate() in Code.gs, which already has a test suite behind it. If you find
   yourself writing an "if level" check in here, stop — it belongs there.
--------------------------------------------------------------------------- */


/**
 * Serves the page. Google calls this when someone opens the web app URL.
 *
 * The card code arrives as ?card=CODE, which is what the printed QR carries.
 * Treat it as hostile: it is whatever a stranger typed into a URL bar.
 *
 * The parameter is deliberately not called "c". A single-letter c returns HTTP
 * 400 on Google-hosted URLs — reproducible against both this app and an
 * ordinary Google Form, so it is not something this script can fix. Every
 * other name tested behaves normally, and there is nothing to gain from the
 * short one.
 */
function doGet(e) {
  const code = ((e && e.parameter && e.parameter.card) || '').trim().toUpperCase();

  const page = HtmlService.createTemplateFromFile('Index');
  page.code = code;
  page.card = code ? lookUpCard(code) : { found: false };

  return page.evaluate()
    .setTitle('Guild Ranks')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}


/**
 * Called from the page via google.script.run when the member submits.
 *
 * The lock matters: two people scanning at the same moment must not both
 * succeed. Sheet reads are not atomic, so without this a shared code could
 * slip through and single-use codes are the whole security model.
 */
function activateCard(code, email) {
  code = String(code || '').trim().toUpperCase();
  email = String(email || '').trim().toLowerCase();

  if (!email) {
    return { result: 'rejected', reason: 'Enter your email to activate.' };
  }

  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
  } catch (err) {
    return { result: 'rejected', reason: 'Busy right now — try again in a moment.' };
  }

  try {
    const outcome = validate(code, email);
    log(code, email, outcome.result, outcome.reason);
    return outcome;
  } finally {
    lock.releaseLock();
  }
}


/** Lets Index.html pull in separate CSS/JS files if you split them out. */
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
