#!/usr/bin/env python
"""A simple script for calculating ACB and capital gains/losses for stock
market trades.
"""

import copy
import datetime
import logging
import os
import sys

import acb.cibc
import acb.common
import acb.currency
import acb.mssb

from collections import namedtuple


# Ensure that the current directory is able to be imported from. This allows us
# to bring in our various modules as imports.
SELF_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, SELF_DIR)


LOGGER = logging.getLogger(__name__)


# Adjusted cost base. This is implicitly in CAD.
AdjustedCostBase = namedtuple(
    'AdjustedCostBase',
    'units cost')


# A special kind of transaction that will invoke a functor.
TransactionFunctor = namedtuple(
    'TransactionFunctor',
    'date settlement_date function')


# TODO: Handle capital gains/losses here as well.
def GoogleSplit(date, acbs, cg, shares, when):
  """Applies the stock split to ACBs and capital gains/losses."""
  if 'GOOG' in acbs:
    a = acbs['GOOG']
    cost_per_share = acb.common.CurrencyAmount('USD', 0.001)
    cost_per_share = acb.currency.Convert(
        cost_per_share, 'CAD', date, when)
    # Class A GOOG shares become Class A GOOGL shares, and retain their
    # original cost base.
    acbs['GOOGL'] = a
    # One GOOG class C share is awarded per Class A GOOG share. These are
    # a dividend with a par value of USD 0.001.
    acbs['GOOG'] = AdjustedCostBase(
        a.units, a.units * cost_per_share.amount)

  # TODO: Handle the capital gains of the dividend!

  # Issue GOOGL shares.
  if 'GOOG' in shares:
    # Create a clone of the list so that modifying one doesn't affect
    # the other.
    shares['GOOGL'] = copy.deepcopy(shares['GOOG'])


def PushShares(shares, units, value, date):
  """Pushes shares to a stack of purchases."""
  if len(shares) == 0 or shares[-1][0] != date:
    shares.append([date, units, value])
    return
  shares[-1][1] += units
  shares[-1][2] += units * value


def PopShares(shares, units, count_since):
  """Pops shares from a stack of purchases.
  
  Returns the number and value of shares that covered the sale that had been
  acquired >= |count_since|.
  """
  net_units = 0
  net_value = 0
  buy_date = None

  # Pop off old batches of shares until the last batch is big
  # enough to cover the remaining sale.
  while shares[-1][1] < units:
    units -= shares[-1][1]
    buy_date = shares[-1][0]
    if shares[-1][0] >= count_since:
      net_units += shares[-1][1]
      net_value += shares[-1][2]
    del shares[-1]

  # At this point the current acquisition will cover the sale.
  # Remove the shares and return the date.
  new_units = shares[-1][1] - units
  new_value = shares[-1][2] * new_units / shares[-1][1]
  delta_value = shares[-1][2] - new_value
  buy_date = shares[-1][0]
  shares[-1][1] = new_units
  shares[-1][2] = new_value
  if shares[-1][0] >= count_since:
    net_units += units
    net_value += delta_value
  if shares[-1][1] == 0:
    del shares[-1]
  return (buy_date, net_units, net_value)


def SumShares(shares):
  """Sums the shares in a stack of purchases."""
  net = 0
  for (date, units) in shares:
    net += units
  return net


DEFAULT_RATE = 'daily noon'


def ProcessTransactions(txs, display=False):
  """Process the list of transactions, using the provided conversion rates."""
  acbs = {}
  cgs = {}
  shares = {}

  # An event is a capital gains/loss generating sale. Multiple events that occur
  # for the same property type on the same day can be folded.
  events = {}
  
  for tx in txs:
    date = tx.settlement_date

    # Handle transaction functors.
    if type(tx) == TransactionFunctor:
      tx.function(date, acbs, cgs, shares, DEFAULT_RATE)
      continue

    # Get the fees in our local currency.
    fees = acb.currency.Convert(
        tx.fees, 'CAD', date, DEFAULT_RATE)
    
    # Ensure there's an ACB entry for this symbol.
    a = acbs.get(tx.symbol, AdjustedCostBase(0.0, 0.0))
    
    # Ensure there's a capital gains entry for this year.
    y = date.year
    if y not in cgs:
      cgs[y] = 0.0
  
    # Ensure there's a shares stack for this year.
    if tx.symbol not in shares:
      shares[tx.symbol] = []

    if (tx.type == acb.common.TRANS_ACQUIRE or
        tx.type == acb.common.TRANS_BUY):
      # TODO: Handle buys within 30 days of an equivalent sale. The losses
      # from the corresponding sale have to be ignored and instead pushed
      # into the ACB.
      value = acb.currency.Convert(
          tx.value, 'CAD', date, DEFAULT_RATE)
      a = AdjustedCostBase(
          a.units + tx.units,
          a.cost + tx.units * value.amount + fees.amount)
      PushShares(shares[tx.symbol], tx.units, tx.units * value.amount, date)
    elif tx.type == acb.common.TRANS_SELL:
      (buy_date, washed_units, washed_value) = PopShares(
          shares[tx.symbol], tx.units, date - datetime.timedelta(days=30))

      # TODO(chrisha): Optionally wash sales against the most recent
      # purchases.

      value = acb.currency.Convert(
          tx.value, 'CAD', date, DEFAULT_RATE)
      cost_per_unit = a.cost / a.units
      units = max(0, a.units - tx.units)
      cost = max(0, a.cost * units / a.units)
      
      # Update the ACB.
      a = AdjustedCostBase(units, cost)
      
      # Calculate capital gains or losses.
      cg = (value.amount - cost_per_unit) * tx.units - fees.amount
        
      cgs[y] += cg
      
      if cg != 0 and display:
        # Ensure there's an event for this day and property.
        if date not in events:
          events[date] = {}
        if tx.symbol not in events[date]:
          events[date][tx.symbol] = {
            'units': 0,
            'acquisition': buy_date,
            'proceeds': 0,
            'acb': 0,
            'expenses': 0,
            'lots': 0,
          }

        # Get the existing event.
        evt = events[date][tx.symbol]
        evt['units'] += tx.units
        evt['acquisition'] = max(evt['acquisition'], buy_date)
        evt['proceeds'] += (value.amount * tx.units)
        evt['acb'] += (cost_per_unit * tx.units)
        evt['expenses'] += fees.amount
        evt['lots'] += 1
    elif tx.type == acb.common.TRANS_CAPITAL_RETURN:
      # Simply decrease the adjusted cost base by the amount of the capital
      # return.
      value = acb.currency.Convert(
          tx.value, 'CAD', date, DEFAULT_RATE)
      a = acbs[tx.symbol]
      cost = max(0, a.cost - value.amount)
      a = AdjustedCostBase(a.units, cost)
    elif tx.type == acb.common.TRANS_DIVIDEND:
      # TODO(chrisha): Handle dividends properly. Banks actually issue
      # T3s for this, so not entirely necessary.
      continue
    else:
      raise Exception('Unknown transaction type: %s' % tx.type)

    acbs[tx.symbol] = a

  if False:
    for date in sorted(events.keys()):
      for prop in sorted(events[date].keys()):
        evt = events[date][prop]
        print 'Capital Gains/Loss Event'
        print 'Property   : %s' % prop
        print 'Units      : %.2f' % evt['units']
        print 'Acquisition: %s' % evt['acquisition'].strftime('%d-%m-%Y')
        print 'Settlement : %s' % date.strftime('%d-%m-%Y')
        print 'Proceeds   : $%.2f' % evt['proceeds']
        print 'ACB        : $%.2f' % evt['acb']
        print 'ACB/unit   : $%.2f' % (evt['acb'] / evt['units'])
        print 'Expenses   : $%.2f' % evt['expenses']
        print 'Lots       : %d' % evt['lots']
        print ''

  # Roll up events by year and property symbol.
  years = {}
  for date in sorted(events.keys()):
    y = date.year
    if y not in years:
      years[y] = {}
    props = years[y]

    for prop in sorted(events[date].keys()):
      evt = events[date][prop]

      if prop not in props:
        props[prop] = copy.deepcopy(evt)
        props[prop]['transactions'] = 1
        del props[prop]['acquisition']
        del props[prop]['lots']
      else:
        net = props[prop]
        net['units'] += evt['units']
        net['proceeds'] += evt['proceeds']
        net['acb'] += evt['acb']
        net['expenses'] += evt['expenses']
        net['transactions'] += 1

  # Output an annualized list of capital gains events.
  for year in sorted(years.keys()):
    print 'Annualized Capital Gain/Loss Events For %d\n' % year
    props = years[year]
    for prop in sorted(props.keys()):
      evt = props[prop]
      g = evt['proceeds'] - evt['acb'] - evt['expenses']
      print 'Property    : %s' % prop
      print 'Units       : %.2f' % evt['units']
      print 'Proceeds    : $%.2f' % evt['proceeds']
      print 'ACB         : $%.2f' % evt['acb']
      print 'Expenses    : $%.2f' % evt['expenses']
      print 'Transactions: %d' % evt['transactions']
      print 'Gains       : $%.2f' % g
      print ''

  # Roll up events by year and property symbol.
      
  
  # Return the summarys status after processing the shares.
  return (acbs, cgs, shares)


def PrintSummary(acbs, cgs, shares):
  """Print a summary of the status."""
  print 'Current Adjusted Cost Bases'
  for sym in sorted(acbs.keys()):
    a = acbs[sym]
    if a.units == 0:
      continue
    print "%s: units=%d cost=%.2f cost_per_unit=%.2f" % (
        sym, a.units, a.cost, a.cost / a.units)
  print ''
  
  print 'Capital Gains Record'
  total_cg = 0
  for year in sorted(cgs.keys()):
    cg = cgs[year]
    total_cg += cg
    print "%d: capital_gains=%.2f" % (year, cg)
  print "sum : capital_gains=%.2f" % (total_cg)
  print ''


if __name__ == '__main__':
  txs = []

  for f in sys.argv[1:]:
    b = os.path.basename(f)
    importer = None
    if b.lower().startswith('mssb'):
      importer = acb.mssb
    elif b.lower().startswith('cibc'):
      importer = acb.cibc
    else:
      raise Exception('No importer for file: %s' % f)
    importer.Process(open(f, 'rb'), lambda tx: txs.insert(0, tx))

  if len(txs) == 0:
    raise Exception('No transactions to process.')
 
  d = datetime.datetime(year=2014, month=4, day=2)
  txs.append(TransactionFunctor(date=d, settlement_date=d,
                                function=GoogleSplit))

  # TODO: Process buys and sells on the same day such that the
  # oldest shares are sold first. That is, always process sales first
  # unless there's insufficient stock to handle the sale. In which case,
  # process buys until there's just enough.
  
  txs = sorted(txs, acb.common.TransactionComparator)

  # Process the transactions.
  acbs, cgs, shares = ProcessTransactions(txs, display=True)
  PrintSummary(acbs, cgs, shares)
