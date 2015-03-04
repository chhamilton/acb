#!/usr/bin/env python
"""A simple script for calculating ACB and capital gains/losses for stock
market trades.
"""

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
		'date function')


# TODO: Handle capital gains/losses here as well.
def GoogleSplit(date, acbs, cg, shares):
	"""Applies the stock split to ACBs and capital gains/losses."""
	if 'GOOG' in acbs:
		a = acbs['GOOG']
		cost_per_share = acb.common.CurrencyAmount('USD', 0.001)
		cost_per_share = acb.currency.Convert(
				cost_per_share, 'CAD', date, 'high')
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
		shares['GOOGL'] = shares['GOOG'][:]

		
def PushShares(shares, units, date):
	"""Pushes shares to a stack of purchases."""
	if len(shares) == 0 or shares[-1][0] != date:
		shares.append([date, units])
		return
	shares[-1][1] += units

	
def PopShares(shares, units):
	"""Pops shares from a stack of purchases.
	
	Returns the date of the furthest acquisition required to
	cover the sale.
	"""
	# Pop off old batches of shares until the last batch is big
	# enough to cover the remaining sale.
	while shares[-1][1] < units:
		units -= shares[-1][1]
		del shares[-1]

	# At this point the current acquisition will cover the sale.
	# Remove the shares and return the date.
	shares[-1][1] -= units
	date = shares[-1][0]
	if shares[-1][1] == 0:
		del shares[-1]
	return date


def SumShares(shares):
	"""Sums the shares in a stack of purchases."""
	net = 0
	for (date, units) in shares:
		net += units
	return net


if __name__ == '__main__':
	txs = [TransactionFunctor(
			date=datetime.datetime(year=2014, month=4, day=2),
			function=GoogleSplit)]

	# Load the MSSB transactions. These are in reverse chronological order.
	acb.mssb.Process(open('mssb.csv', 'rb'), lambda tx: txs.insert(0, tx))
	
	# Load CIBC transactions. These are also in reverse chronological order.
	acb.cibc.Process(open('cibc.csv', 'rb'), lambda tx: txs.insert(0, tx))

	# TODO: Process buys and sells on the same day such that the
	# oldest shares are sold first. That is, always process sales first
	# unless there's insufficient stock to handle the sale. In which case,
	# process buys until there's just enough.
	
	txs = sorted(txs, acb.common.TransactionComparator)

	acbs = {}
	cgs = {}
	shares = {}
	for tx in txs:
		# Handle transaction functors.
		if type(tx) == TransactionFunctor:
			tx.function(tx.date, acbs, cgs, shares)
			continue
		
		# Get the fees in our local currency.
		fees = acb.currency.Convert(tx.fees, 'CAD', tx.date, 'high')
		
		# Ensure there's an ACB entry for this symbol.
		a = acbs.get(tx.symbol, AdjustedCostBase(0.0, 0.0))
		
		# Ensure there's a capital gains entry for this year.
		y = tx.date.year
		if y not in cgs:
			cgs[y] = 0.0
	
		# Ensure there's a shares stack for this year.
		if tx.symbol not in shares:
			shares[tx.symbol] = []

		if (tx.type == acb.common.TRANS_ACQUIRE or
				tx.type == acb.common.TRANS_BUY):
			value = acb.currency.Convert(tx.value, 'CAD', tx.date, 'high')
			a = AdjustedCostBase(
					a.units + tx.units,
					a.cost + tx.units * value.amount + fees.amount)
			PushShares(shares[tx.symbol], tx.units, tx.date)
		elif tx.type == acb.common.TRANS_SELL:
			buy_date = PopShares(shares[tx.symbol], tx.units)
			days_since_buy = (tx.date - buy_date).days
	
			# Use the lowest rate of the day for sales.
			value = acb.currency.Convert(tx.value, 'CAD', tx.date, 'low')
			cost_per_unit = a.cost / a.units
			units = a.units - tx.units
			
			# Update the ACB.
			a = AdjustedCostBase(units, cost_per_unit * units)
			
			# Calculate capital gains or losses.
			cg = (value.amount - cost_per_unit) * tx.units - fees.amount
			if cg > 0 and days_since_buy <= 30:
				# TODO: Is this legal?
				pass
			else:
				cgs[y] += cg

		acbs[tx.symbol] = a

	print 'Current Adjusted Cost Bases'
	for sym in sorted(acbs.keys()):
		a = acbs[sym]
		if a.units == 0:
			continue
		print "%s: units=%d cost=%.2f cost_per_unit=%.2f" % (
				sym, a.units, a.cost, a.cost / a.units)
	print ''
	
	print 'Capital Gains Record'
	for year in sorted(cgs.keys()):
		cg = cgs[year]
		print "%d: capital_gains=%.2f" % (year, cg)
	print ''

	print 'Current Shares held'
	for sym in sorted(shares.keys()):
		if len(shares[sym]) == 0:
			continue
		print sym + ' ' + str(SumShares(shares[sym]))
		for (date, units) in shares[sym]:
			print date.strftime('  %Y/%m/%d ') + str(units)
	print ''