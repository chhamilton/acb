#!/usr/bin/env python
"""A simple script for calculating ACB and capital gains/losses for stock
market trades.
"""

import logging
import os
import sys

import acb.common
import acb.currency
import acb.mssb


# Ensure that the current directory is able to be imported from. This allows us
# to bring in our various modules as imports.
SELF_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, SELF_DIR)


LOGGER = logging.getLogger(__name__)


if __name__ == '__main__':

	acb.mssb.Process(open('mssb.csv', 'rb'), Print)