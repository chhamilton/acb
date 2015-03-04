#!/usr/bin/env python
"""Utility functions for retrieving currency conversion rates online."""

import csv
import datetime
import logging
import os
import urllib2

import sys
print sys.path

import acb.memo


LOGGER = logging.getLogger(__name__)


# Bank of Canada's URL for downloading US dollar rates as a CSV file.
# The date is to be expanded using strftime.
BOC_URL = ('http://www.bankofcanada.ca/stats/results//csv?lP='
				   'lookup_daily_exchange_rates.php'
           '&sR=2005-03-02&se=_0101-_0102-_0103-_0104&dF=%Y-%m-%d&dT=')


@acb.memo.memo
@acb.memo.memosql
def GetUsdToCadRateTable(date):
	"""Gets the full table of USD -> CAD currency rates.
	
	Returns:
		A list of (date, noon, close, high, low) rates. The date may be earlier
		than the requested date due if the requested day is a bank holiday.
	
	Note:
		This function is memoized to memory and to a persistent database.
	"""
	url = date.strftime(BOC_URL)
	LOGGER.debug('Requesting Bank of Canada USD to CAD rates for %s.', date)
	reader = csv.reader(urllib2.urlopen(url))
	for row in reader:
		if len(row) > 8 and row[0] == 'Low':
			noon = float(row[2])
			close = float(row[4])
			high = float(row[6])
			low = float(row[8])

			# Negative values are returned for bank holidays. Use the
			# previously known closing rate. This will recurse until the
			# closest earlier banking day is found.
			if noon < 0:
				LOGGER.debug('%s was a bank holiday, checking the day before.', date)
				previous_day = date - datetime.timedelta(days=1)
				rates = GetUsdToCadRateTable(previous_day)
				# Use the previous closing rate as the exact rate for a banking holiday.
				return [previous_day, rates[2], rates[2], rates[2], rates[2]]

			return [date, noon, close, high, low]
	
	raise Exception('Rates not found in downloaded data.')

			
def GetConversionRateTable(currency_from, currency_to, date):
	"""Returns the conversion rate table from |currency_from| to |currency_to|.
	
	Args:
		currency_from: The currency to convert from.
		currency_to: The currency to convert to.
		date: The date of the query.

	Returns:
		A list of values of one unit of |currency_from| in |currency_to|. Various
		rates are retrieved, including the noon rate, day close rate, the day's
		highest rate and the day's lowest rate. The date of the rate retrieval is
		also returned, as the original requested date may have been a bank holiday.
		The data is returned in the following format:
		
			(date, noon, close, high, low)
	"""
	if currency_from == 'USD' and currency_to == 'CAD':
		rates = GetUsdToCadRateTable(date)
		return rates
	elif currency_from == 'CAD' and currency_to == 'USD':
		rates = GetUsdToCadRateTable(date)
		# Invert the rates.
		rates = [rates[0], 1.0/rates[1], 1.0/rates[2], 1.0/rates[4], 1.0/rates[3]]
		return rates
	else:
		raise Exception('Unsupported conversion: %s -> %s' % (currency_from, currency_to))


def GetConversionRate(currency_from, currency_to, date, when='noon'):
	"""Returns the conversion rate from |currency_from| to |currency_to|.
	
	Args:
		currency_from: The currency to convert from.
		currency_to: The currency to convert to.
		date: The date of the query.
		when: The time of the exchange. This may be one of
		      'low', 'high', 'noon' or 'close'.

	Returns:
		The value of one unit of |currency_from| in |currency_to|, at the provided
		time |when|.
	"""
	try:
		idx = ['noon', 'close', 'high', 'low'].index(when) + 1
	except ValueError:
		raise Exception('Invalid when: %s' % when)
	
	rates = GetConversionRateTable(currency_from, currency_to, date)
	return rates[idx]

		
if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)

	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2015, month=1, day=1), 'noon')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2015, month=1, day=1), 'close')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2015, month=1, day=1), 'high')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2015, month=1, day=1), 'low')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=12, day=31), 'noon')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=12, day=31), 'close')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=12, day=31), 'high')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=12, day=31), 'low')

	acb.memo.KillDatabase(GetUsdToCadRateTable)