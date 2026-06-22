/** Google Sheet watcher for notify-hub. */

var NOTIFY_HUB = {
  sheetId: 543845934,
  stateKey: 'NOTIFY_HUB_LAST_SUCCESS',
  categoryNames: ['交', '食', '日', '保險', '運'],
  retryDelaysMs: [0, 1000, 2000]
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Notify Hub')
    .addItem(
      '安裝觸發器並立即推播',
      'installNotifyHub'
    )
    .addItem('立即推播', 'sendNow')
    .addToUi();
}

function installNotifyHub() {
  var spreadsheet = SpreadsheetApp.getActive();
  var handlers = [
    'handleSheetEdit',
    'handleSheetChange',
    'handleFormSubmit'
  ];
  var triggers = ScriptApp.getProjectTriggers();

  triggers.forEach(function(trigger) {
    var handler = trigger.getHandlerFunction();
    if (handlers.indexOf(handler) !== -1) {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  ScriptApp.newTrigger('handleSheetEdit')
    .forSpreadsheet(spreadsheet)
    .onEdit()
    .create();

  ScriptApp.newTrigger('handleSheetChange')
    .forSpreadsheet(spreadsheet)
    .onChange()
    .create();

  ScriptApp.newTrigger('handleFormSubmit')
    .forSpreadsheet(spreadsheet)
    .onFormSubmit()
    .create();

  processBudgetSummary_(true);
  SpreadsheetApp.getUi().alert(
    'Notify Hub 已安裝並完成首次推播。'
  );
}

function handleSheetEdit() {
  processBudgetSummary_(false);
}

function handleSheetChange() {
  processBudgetSummary_(false);
}

function handleFormSubmit() {
  Utilities.sleep(1500);
  processBudgetSummary_(false);
}

function sendNow() {
  processBudgetSummary_(true);
}

function processBudgetSummary_(forceSend) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) {
    console.log('Notify Hub is already running.');
    return;
  }

  try {
    SpreadsheetApp.flush();
    var payload = readBudgetSummary_();
    var canonical = JSON.stringify(payload);
    var props = PropertiesService.getScriptProperties();
    var previous = props.getProperty(
      NOTIFY_HUB.stateKey
    );

    if (!forceSend && previous === canonical) {
      return;
    }

    postNotification_(payload);
    props.setProperty(
      NOTIFY_HUB.stateKey,
      canonical
    );
  } finally {
    lock.releaseLock();
  }
}

function getTargetSheet_() {
  var sheets = SpreadsheetApp.getActive().getSheets();
  for (var i = 0; i < sheets.length; i += 1) {
    if (sheets[i].getSheetId() === NOTIFY_HUB.sheetId) {
      return sheets[i];
    }
  }
  throw new Error('Target sheet was not found.');
}

function readBudgetSummary_() {
  var sheet = getTargetSheet_();
  var totals = sheet
    .getRange('M2:O2')
    .getValues()[0];
  var rows = sheet
    .getRange('P2:Q6')
    .getValues();
  var categories = {};

  rows.forEach(function(row, index) {
    var expected = NOTIFY_HUB.categoryNames[index];
    var actual = String(row[0]).trim();
    if (actual !== expected) {
      throw new Error(
        'Category mismatch at row ' + (index + 2)
      );
    }
    var cellName = 'Q' + (index + 2);
    categories[expected] = roundMoney_(
      row[1],
      cellName
    );
  });

  return {
    type: 'budget_summary',
    total_expense: roundMoney_(
      totals[0],
      'M2'
    ),
    total_income: roundMoney_(
      totals[1],
      'N2'
    ),
    balance: roundMoney_(
      totals[2],
      'O2'
    ),
    categories: categories
  };
}

function roundMoney_(value, cellName) {
  var invalid = value === '';
  invalid = invalid || value === null;
  invalid = invalid || typeof value === 'boolean';
  if (invalid) {
    throw new Error(cellName + ' must be numeric.');
  }

  var number = Number(value);
  if (!isFinite(number)) {
    throw new Error(cellName + ' must be numeric.');
  }

  var sign = number < 0 ? -1 : 1;
  var absolute = Math.abs(number);
  var rounded = Math.round(absolute * 100);
  return sign * rounded / 100;
}

function postNotification_(payload) {
  var props = PropertiesService.getScriptProperties();
  var url = props.getProperty('NOTIFY_API_URL');
  var secret = props.getProperty(
    'NOTIFY_API_SECRET'
  );

  if (!url || !secret) {
    throw new Error('Missing Notify Hub properties.');
  }

  var lastError = null;
  var delays = NOTIFY_HUB.retryDelaysMs;
  for (var attempt = 0;
       attempt < delays.length;
       attempt += 1) {
    if (delays[attempt] > 0) {
      Utilities.sleep(delays[attempt]);
    }

    try {
      var options = {
        method: 'post',
        contentType: 'application/json',
        headers: {
          'X-Notify-Secret': secret
        },
        payload: JSON.stringify(payload),
        muteHttpExceptions: true
      };
      var response = UrlFetchApp.fetch(
        url,
        options
      );
      var status = response.getResponseCode();
      if (status >= 200 && status < 300) {
        return;
      }

      var responseText = response.getContentText();
      var message = 'notify-hub HTTP ' + status;
      message += ': ' + responseText;
      if (status !== 429 && status < 500) {
        throw new Error(message);
      }
      lastError = new Error(message);
    } catch (error) {
      var errorText = String(error.message || '');
      var clientError = errorText.indexOf(
        'notify-hub HTTP 4'
      ) === 0;
      if (clientError) {
        throw error;
      }
      lastError = error;
    }
  }

  if (lastError) {
    throw lastError;
  }
  throw new Error('Notify Hub request failed.');
}
