#!/usr/bin/env python
"""Common definitions.
"""

import logging
from collections import namedtuple


LOGGER = logging.getLogger(__name__)


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
#   symbol: The name of the property (usually ticker symbol).
#   type: The type of the transaction, from the TRANS_ enum. 
#   units: The number of items of property involved in the transaction.
#   value: Per property item value, as a CurrencyAmount.
#   fees: Any fees associated with the transaction, as a CurrencyAmount.
Transaction = namedtuple(
		'Transaction',
		'date symbol type units value fees')


def TransactionComparator(tx1, tx2):
	"""Transaction comparator.
	
	Stably sorts by increasing dates.
	"""
	if tx1.date < tx2.date:
		return -1
	elif tx1.date == tx2.date:
		return 0
	else:
		return 1