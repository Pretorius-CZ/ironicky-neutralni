/**
 * Google Apps Script — spustí GitHub Actions workflow "Publikovat denní citát"
 * každý den v 18:00 (Europe/Prague).
 *
 * NASTAVENÍ:
 * 1) script.google.com -> New project
 * 2) Vlož tento kód, doplň TOKEN (GitHub PAT s právem "Actions: write")
 * 3) Project Settings -> Time zone: Europe/Prague
 * 4) Spusť funkci setupTrigger() (jednou) - vytvoří denní trigger v 18:00
 * 5) Ověř: spusť publishDaily() ručně -> v GitHub Actions by měl naskočit běh
 */

const OWNER = 'Pretorius-CZ';
const REPO = 'ironicky-neutralni';
const WORKFLOW = 'publish.yml';        // soubor workflow v .github/workflows/
const BRANCH = 'main';
const TOKEN = 'SEM_VLOZ_GITHUB_PAT';   // GitHub Personal Access Token

function publishDaily() {
  var url = 'https://api.github.com/repos/' + OWNER + '/' + REPO +
            '/actions/workflows/' + WORKFLOW + '/dispatches';
  var resp = UrlFetchApp.fetch(url, {
    method: 'post',
    headers: {
      'Authorization': 'Bearer ' + TOKEN,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    },
    contentType: 'application/json',
    payload: JSON.stringify({ ref: BRANCH }),
    muteHttpExceptions: true
  });
  Logger.log('HTTP ' + resp.getResponseCode() + ' | ' + resp.getContentText());
}

function setupTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('publishDaily')
    .timeBased()
    .atHour(18)
    .everyDays(1)
    .inTimezone('Europe/Prague')
    .create();
  Logger.log('Trigger nastaven: denne 18:00 Europe/Prague');
}
