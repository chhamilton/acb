#!/usr/bin/env python
"""A simple module for parsing Morgan Smith Stanley Barney RSU transaction
history CSV files.
"""

import common
import csv
import datetime
import sys


MSSB_DATE = re.compile('^[01][0-9]/[0123][0-9]/20\d{2}$')
MSSB_DOLLAR = re.compile('[^0-9.]')
MSSB_PLAN_TO_NAME = {
		'Historical GSU': 'GOOG.presplit',
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