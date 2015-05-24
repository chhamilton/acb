#!/usr/bin/env python
"""A simple module for parsing CIBC Investors Edge transaction history CSV
files.
"""

import csv
import datetime
import re

import acb.common


CIBC_DATE = re.compile('^[A-Za-z]+ [0123][0-9], 20\d{2}$')
CIBC_TX_TYPES = {'Sell': acb.common.TRANS_SELL,
							   'Buy': acb.common.TRANS_BUY}
CIBC_NUMBER = re.compile('[^0-9.]')


def InferSymbol(d):
	if 'Symbol' in d:
		return d['Symbol']

	# Handle Horizons ETF.
	if d['Description'].startswith('HORIZONS U S DLR CURRENCY ETF'):
		return 'DLR'

	raise Exception('Unknown property: %s' % d['Description'])

	
def Process(src, func):
	"""Parses data from a CIBC Investors Edge exported CSV file.
	
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
		if len(row) > 0 and row[0] == 'Transaction Date':
			break
	header = row
	
	# Read the records.
	for row in reader:
		# Continue as long as we encounter valid records.
		if len(row) == 0 or not CIBC_DATE.match(row[0]):
			break
		d = {}
		for i in xrange(min(len(header), len(row))):
			if row[i]:
				d[header[i]] = row[i]

		# Parse the transaction type.
		tx_type = CIBC_TX_TYPES.get(d['Transaction Type'], None)
		if tx_type == None:
			continue
				
		# Parse the transaction date and symbol.
		day = datetime.datetime.strptime(d['Transaction Date'], '%B %d, %Y')
		sym = InferSymbol(d)

		u = float(CIBC_NUMBER.sub('', d['Quantity']))
		if int(u) == u:
			u = int(u)
		v = float(CIBC_NUMBER.sub('', d['Price']))
		f = float(CIBC_NUMBER.sub('', d['Commission']))
		t = acb.common.Transaction(
				date=day,
				symbol=sym,
				type=tx_type,
				units=u,
				value=acb.common.CurrencyAmount(d['Currency of Amount'], v),
				fees=acb.common.CurrencyAmount('CAD', f))
		func(t)