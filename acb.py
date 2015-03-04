#!/usr/bin/env python
"""A simple script for calculating ACB and capital gains/losses for stock
market trades.
"""

import logging
import mssb


LOGGER = logging.getLogger(__name__)


if __name__ == '__main__':
	def Print(x):
		print x

	mssb.Process(open('mssb.csv', 'rb'), Print)