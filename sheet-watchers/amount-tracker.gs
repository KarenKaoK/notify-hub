/** Google Sheet watcher for notify-hub. */

var NOTIFY_HUB = {
  sheetId: 543845934,
  stateKey: 'NOTIFY_HUB_LAST_SUCCESS',
  categoryStartRow: 2,
  categoryNameColumn: 16,
  retryDelaysMs: [0, 1000, 2000]
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Notify Hub')
    .addItem(
      '\u5b89\u88dd\u89f8\u767c\u5668\u4e26\u7acb\u5373\u63a8\u64ad',
      'installNotifyHub'
    )
    .addItem('\u7acb\u5373\u63a8\u64ad', 'sendNow')
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
    'Notify Hub ' +
    '\u5df2\u5b89\u88dd\u4e26\u5b8c\u6210\u9996\u6b21\u63a8\u64ad\u3002'
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
  var rows = readCategoryRows_(sheet);
  var categories = {};
  var seen = {};

  rows.forEach(function(row, index) {
    var actual = String(row[0]).trim();
    var value = row[1];
    var rowNumber = index + NOTIFY_HUB.categoryStartRow;

    if (!actual) {
      return;
    }
    if (actual === '\u5206\u985e' || actual === 'Category') {
      return;
    }
    if (seen[actual]) {
      throw new Error(
        'Duplicate category at row ' + rowNumber + ': ' + actual
      );
    }

    seen[actual] = true;
    var cellName = 'Q' + rowNumber;
    categories[actual] = roundMoney_(
      value,
      cellName
    );
  });

  if (Object.keys(categories).length === 0) {
    throw new Error('No budget categories were found.');
  }

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

function readCategoryRows_(sheet) {
  var lastRow = sheet.getLastRow();
  var startRow = NOTIFY_HUB.categoryStartRow;
  if (lastRow < startRow) {
    return [];
  }

  var rowCount = lastRow - startRow + 1;
  return sheet
    .getRange(
      startRow,
      NOTIFY_HUB.categoryNameColumn,
      rowCount,
      2
    )
    .getValues();
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
    } catch (err) {
      var errorText = String(err.message || '');
      var clientError = errorText.indexOf(
        'notify-hub HTTP 4'
      ) === 0;
      if (clientError) {
        throw err;
      }
      lastError = err;
    }
  }

  if (lastError) {
    throw lastError;
  }
  throw new Error('Notify Hub request failed.');
}
