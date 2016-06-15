#!/usr/bin/env python
"""A simple module for parsing Morgan Smith Stanley Barney RSU transaction
history CSV files.
"""

import csv
import datetime
import re

import acb.common
import acb.date


MSSB_DATE = re.compile('^[01][0-9]/[0123][0-9]/20\d{2}$')
MSSB_DOLLAR = re.compile('[^0-9.]')
MSSB_PLAN_TO_NAME = {
    'Historical GSU': 'GOOG',
    'GSU Class A': 'GOOGL',
    'GSU Class C': 'GOOG'}


def Process(src, func):
  """Parses data from a MSSB exported CSV file.
  
  Reads lines from the provided |src| (an IO object), parses records, and emits
  them to the provided |func|. Each record is emitted as a dict in the documented
  format.
  
  Args:
    src: An input IO object.
    func: A function that will receive 
  """
  reader = csv.reader(src)
  
  # Find the header line.
  for row in reader:
    if len(row) > 0 and row[0] == 'Date':
      break
  header = row

  # Read the records.
  for row in reader:
    # Continue as long as we encounter valid records.
    if len(row) == 0 or not MSSB_DATE.match(row[0]):
      break
    d = {}
    for i in xrange(min(len(header), len(row))):
      if row[i]:
        d[header[i]] = row[i]
  
    # Parse the transaction date.
    day = datetime.datetime.strptime(d['Date'], '%m/%d/%Y')
    
    # A vesting event with withheld shares.
    if d.get('Tax Payment Method', None) == 'Withhold to Cover':
      # The stock symbol.
      s = MSSB_PLAN_TO_NAME[d['Plan']]
      # The number of shares that vested.
      u = int(float(d['Quantity']))
      # The vesting price.
      v = float(MSSB_DOLLAR.sub('', d['Price']))
      # Remaining shares after the withhold.
      r = int(float(d['Net Share Proceeds']))
      # The number of withheld shares.
      w = u - r

      if True:
        # Emit a single transaction with the withholding already taken into
        # account.
        t = acb.common.Transaction(
            date=day,
            settlement_date=day,
            symbol=s,
            type=acb.common.TRANS_ACQUIRE,
            units=r,
            value=acb.common.CurrencyAmount('USD', v),
            fees=acb.common.CurrencyAmount('USD', 0.0))
        func(t)
      else:
        # Emit a sell transaction for the tax withholding.
        t = acb.common.Transaction(
            date=day,
            # The settlement is the same day as the acquisition.
            settlement_date=day,
            symbol=s,
            type=acb.common.TRANS_SELL,
            units=w,
            value=acb.common.CurrencyAmount('USD', v),
            fees=acb.common.CurrencyAmount('USD', 0.0))
        func(t)

        # Emit a acquisition transaction.
        t = acb.common.Transaction(
            date=day,
            settlement_date=day,
            symbol=s,
            type=acb.common.TRANS_ACQUIRE,
            units=u,
            value=acb.common.CurrencyAmount('USD', v),
            fees=acb.common.CurrencyAmount('USD', 0.0))
        func(t)
    elif d['Type'] == 'Sale':
      u = int(float(d['Quantity']))
      v = float(MSSB_DOLLAR.sub('', d['Price']))
      p = float(MSSB_DOLLAR.sub('', d['Net Cash Proceeds']))
      f = u * v - p
      t = acb.common.Transaction(
          date=day,
          settlement_date=acb.date.AddBusinessDays(day, acb.date.SETTLE_DAYS),
          symbol=MSSB_PLAN_TO_NAME[d['Plan']],
          type=acb.common.TRANS_SELL,
          units=u,
          value=acb.common.CurrencyAmount('USD', v),
          fees=acb.common.CurrencyAmount('USD', f))
      func(t)
    elif d['Type'] == 'Cash in Lieu':
      v = float(MSSB_DOLLAR.sub('', d['Net Cash Proceeds']))
      t = acb.common.Transaction(
          date=day,
          settlement_date=day,
          symbol=MSSB_PLAN_TO_NAME[d['Plan']],
          type=acb.common.TRANS_CAPITAL_RETURN,
          units=u,
          value=acb.common.CurrencyAmount('USD', v),
          fees=acb.common.CurrencyAmount('USD', 0.0))
      func(t)
    elif d['Type'] == 'Stock Dividend':
      # TODO(chrisha): Handle dividends with a new event type!
      pass
    elif d['Type'] == 'Released Shares':
      # This is handled via the 'Withhold to Cover' processing above.
      pass
    elif d['Type'] == 'Share Deposit':
      # This is handled via the 'Withhold to Cover' processing above.
      pass
    elif d['Type'] == 'Share Withdrawal':
      # This is handled via the 'Sale' processing above.
      pass
    elif d['Type'] == 'Check':
      # This is handled via the 'Sale' processing above.
      pass
    elif d['Type'] == 'Wire':
      # This is handled via the 'Sale' processing above.
      pass
    else:
      print d
      raise Exception('Unrecognized MSSB transaction type: %s' % d['Type'])
