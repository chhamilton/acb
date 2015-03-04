#!/usr/bin/env python
"""A simple script for calculating ACB and capital gains/losses for stock
market trades.
"""

import csv
import datetime
import os
import re
import urllib2

from collections import namedtuple

# A unit of currency.
CurrencyAmount = namedtuple(
		'CurrencyAmount',
		'currency amount')

# Cost-free acquisition of a property. Similar to a BUY, but the cost is at
# $0 and the event is fully taxable as salary.
TRANS_ACQUIRE = 'ACQUIRE'
# Market purchase of a property.
TRANS_BUY = 'BUY'
# Market sell of a property.
TRANS_SELL = 'SELL'

# Transactions are a named tuple with fields as follows:
#   date: A datetime object.
#   name: The name of the property (usually ticker symbol).
#   type: The type of the transaction, from the TRANS_ enum. 
#   units: The number of items of property involved in the transaction.
#   value: Per property item value, as a CurrencyAmount.
#   fees: Any fees associated with the transaction, as a CurrencyAmount.
#   withheld: A number of shares withheld for tax purposes. This is only
#             filled out for an ACQUIRE transaction.
Transaction = namedtuple(
		'Transaction',
		'date name type units value fees withheld')

MSSB_DATE = re.compile('^[01][0-9]/[0123][0-9]/20\d{2}$')
MSSB_DOLLAR = re.compile('[^0-9.]')
MSSB_PLAN_TO_NAME = {
		'Historical GSU': 'GOOG.presplit',
		'GSU Class A': 'GOOGL',
		'GSU Class C': 'GOOG'}


def ParseMssbCsv(src, func):
	"""Parses data from a MSSB exported CSV file.
	
	Reads lines from the provided |src| (an IO object), parses records, and emits
	them to the provided |func|. Each record is emitted as a dict in the documented
	format.
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
			t = Transaction(
					date=day,
					name=MSSB_PLAN_TO_NAME[d['Plan']],
					type=TRANS_ACQUIRE,
					units=d['Quantity'],
					value=CurrencyAmount('USD', float(MSSB_DOLLAR.sub('', d['Price']))),
					fees=CurrencyAmount('USD', 0.0),
				  withheld=int(float(d['Net Share Proceeds'])))
			func(t)
		elif d['Type'] == 'Sale':
			u = int(d['Quantity'])
			v = float(MSSB_DOLLAR.sub('', d['Price']))
			p = float(MSSB_DOLLAR.sub('', d['Net Cash Proceeds']))
			f = u * v - p
			t = Transaction(
					date=day,
					name=MSSB_PLAN_TO_NAME[d['Plan']],
					type=TRANS_SELL,
					units=u,
					value=CurrencyAmount('USD', v),
					fees=CurrencyAmount('USD', f),
					withheld=0)
			func(t)
		elif d['Type'] == 'Check':
			# TODO: Use 'check' events to calculate currency conversion fees associated
			#       with sale events.
			print d
		else:
			#print d['Type']
			pass

		
def Print(t):
	"""Simple function for printing a value."""
	print t

#ParseMssbCsv(open('mssb.csv', 'rb'), lambda t: t)
GetConversionRate('USD', date=datetime.datetime(year=2014, month=1, day=1))