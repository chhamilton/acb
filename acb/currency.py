#!/usr/bin/env python
"""Utility functions for retrieving currency conversion rates online."""

import csv
import datetime
import logging
import os
import urllib2

import acb.common
import acb.memo


LOGGER = logging.getLogger(__name__)


# Bank of Canada's URL for downloading US dollar rates as a CSV file.
# The date is to be expanded using strftime. They are reported in the
# order (noon, close, high, low).
BOC_DAILY_URL = ('http://www.bankofcanada.ca/stats/results//csv?lP='
				         'lookup_daily_exchange_rates.php'
                 '&sR=2005-03-02&se=_0101-_0102-_0103-_0104&dF=%Y-%m-%d&dT=')

BOC_DAILY_WHENS = ('daily noon', 'daily close', 'daily high', 'daily low')

# BOC URL for downloading monthly exchange rates in CSV format.
# The data is to be expanded using strftime. They are reported in the
# order (noon, close, high, low, 90-day-noon, 90-day-closing).
BOC_MONTHLY_URL = ('http://www.bankofcanada.ca/stats/results//csv?endRange='
		'%Y-%m-01&dFromMonth=%m&dFromYear=%Y&dToMonth=%m&dToYear=%Y&lP='
		'lookup_monthly_exchange_rates.php&sR=2005-04-01&se=L_IEXM0101-L_IEXM0102-'
		'L_IEXM0103-L_IEXM0104-L_IEXM0105-L_IEXM0106')

BOC_MONTHLY_WHENS = ('monthly noon', 'monthly close', 'monthly high',
										 'monthly low', '90-day noon', '90-day close')

# The full list 'whens' for BOC rates.
BOC_WHENS = BOC_DAILY_WHENS + BOC_MONTHLY_WHENS + ('annual',)

# The table of BOC annual USD to CAD exchange rates. Taken from
# http://www.bankofcanada.ca/rates/exchange/annual-average-exchange-rates/
BOC_ANNUAL_RATES = {
	2014: 1.10446640,
	2013: 1.02991480,
	2012: 0.99958008,
	2011: 0.98906920,
}


@acb.memo.memo
@acb.memo.memosql
def GetUsdToCadDailyRateTable(date):
	"""Gets the full table of daily USD -> CAD currency rates.
	
	Returns:
		A list of (date, noon, close, high, low) rates. The date may be earlier
		than the requested date due if the requested day is a bank holiday.
	
	Note:
		This function is memoized to memory and to a persistent database.
	"""
	url = date.strftime(BOC_DAILY_URL)
	LOGGER.debug('Requesting Bank of Canada USD to CAD daily rates for %s.', date)
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
				rates = GetUsdToCadDailyRateTable(previous_day)
				# Use the previous closing rate as the exact rate for a banking holiday.
				return [previous_day, rates[2], rates[2], rates[2], rates[2]]

			return [date, noon, close, high, low]
	
	raise Exception('Rates not found in downloaded data.')


@acb.memo.memo
@acb.memo.memosql
def GetUsdToCadMonthlyRateTable(date):
	"""Gets the full table of monthly USD -> CAD currency rates.
	
	Args:
		date: The date to be queried. Only the month and year will be used so for
		      most efficient caching the date should always be the first of the month.
					This is enforced by raising an exception otherwise.
	
	Returns:
		A list of (noon, close, high, low, 90noon, 90close) rates.
	
	Note:
		This function is memoized to memory and to a persistent database.
	"""
	if date.day != 1:
		raise Exception('Date must be first of the month.')
	url = date.strftime(BOC_MONTHLY_URL)
	LOGGER.debug('Requesting Bank of Canada USD to CAD monthly rates for %s.',
							 date)
	year_month = date.strftime('%Y-%m')
	reader = csv.reader(urllib2.urlopen(url))
	for row in reader:
		if len(row) >= 7 and row[0] == year_month:
			rates = map(lambda x: float(x), row[1:7])
			return rates
	
	raise Exception('Rates not found in downloaded data.')


def GetUsdToCadRateTable(date):
	"""Gets the complete set of USD -> CAD currency rates.
	
	Args:
		date: The data of the query.
	
	Returns:
		A dictionary of rate names to their values.
	"""
	first_of_month = datetime.datetime(year=date.year, month=date.month, day=1)
	dailies = GetUsdToCadDailyRateTable(date)
	monthlies = GetUsdToCadMonthlyRateTable(first_of_month)

	d = {'date': dailies[0] }
	for i in xrange(0, len(BOC_DAILY_WHENS)):
		when = BOC_DAILY_WHENS[i]
		rate = dailies[i + 1]
		d[when] = rate

	for i in xrange(0, len(BOC_MONTHLY_WHENS)):
		when = BOC_MONTHLY_WHENS[i]
		rate = monthlies[i]
		d[when] = rate

	if date.year in BOC_ANNUAL_RATES:
		d['annual'] = BOC_ANNUAL_RATES[date.year]

	return d

			
def GetConversionRateTable(currency_from, currency_to, date):
	"""Returns the conversion rate table from |currency_from| to |currency_to|.
	
	Args:
		currency_from: The currency to convert from.
		currency_to: The currency to convert to.
		date: The date of the query.

	Returns:
		A dict of values of one unit of |currency_from| in |currency_to|. Various
		rates are retrieved, including the noon rate, day close rate, the day's
		highest rate and the day's lowest rate. The date of the rate retrieval is
		also returned, as the original requested date may have been a bank holiday.
		The data as a dictionary mapping rate names to their values, and with a
		'date' key for the actual date associated with the returned rates.
	"""
	# Handle no-op conversions.
	if currency_from == currency_to:
		return [date, 1.0, 1.0, 1.0, 1.0]

	if currency_from == 'USD' and currency_to == 'CAD':
		rates = GetUsdToCadRateTable(date)
		return rates
	elif currency_from == 'CAD' and currency_to == 'USD':
		rates = GetUsdToCadRateTable(date)
		# Invert the rates.
		for k in rates.iterkeys():
			if k != 'date':
				rates[k] = 1.0 / rates[k]
		return rates
	else:
		raise Exception('Unsupported conversion: %s -> %s' % (currency_from, currency_to))


def GetConversionRate(currency_from, currency_to, date, when='daily noon'):
	"""Returns the conversion rate from |currency_from| to |currency_to|.
	
	Args:
		currency_from: The currency to convert from.
		currency_to: The currency to convert to.
		date: The date of the query.
		when: The time of the exchange.

	Returns:
		The value of one unit of |currency_from| in |currency_to|, at the provided
		time |when|.
	"""
	rates = GetConversionRateTable(currency_from, currency_to, date)
	if when not in rates:
		raise Exception('Invalid rate type.')
	return rates[when]


def Convert(currency_amount, currency_to, date, when='daily noon'):
	"""Performs a currency conversion."""
	# Handle no-op conversions.
	if currency_amount.currency == currency_to:
		return currency_amount

	# Handle conversion of no value.
	if currency_amount.amount == 0:
		return acb.common.CurrencyAmount(
				currency_to, 0.0)

	# Get the full conversion rate table.
	rates = GetConversionRateTable(
			currency_amount.currency,
			currency_to,
			date)
	rate = rates[when]
	value = acb.common.CurrencyAmount(
			currency_to, currency_amount.amount * rate)
	return value


if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)

	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=1, day=1), 'daily noon')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=1, day=1), 'daily close')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=1, day=1), 'daily high')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=1, day=1), 'daily low')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=1, day=1), 'monthly noon')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=1, day=1), 'monthly close')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=1, day=1), 'monthly high')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=1, day=1), 'monthly low')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=1, day=1), '90-day noon')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=1, day=1), '90-day close')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2014, month=1, day=1), 'annual')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2013, month=12, day=31), 'daily noon')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2013, month=12, day=31), 'daily close')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2013, month=12, day=31), 'daily high')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2013, month=12, day=31), 'daily low')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2013, month=12, day=31), 'monthly noon')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2013, month=12, day=31), 'monthly close')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2013, month=12, day=31), 'monthly high')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2013, month=12, day=31), 'monthly low')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2013, month=12, day=31), '90-day noon')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2013, month=12, day=31), '90-day close')
	print GetConversionRate('USD', 'CAD', datetime.datetime(year=2013, month=12, day=31), 'annual')

	acb.memo.KillDatabase(GetUsdToCadDailyRateTable)
	acb.memo.KillDatabase(GetUsdToCadMonthlyRateTable)
