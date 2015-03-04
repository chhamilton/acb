#!/usr/bin/env python
"""Python decorators for memoization."""

import base64
import logging
import os
import pickle
import sqlite3
from functools import wraps


LOGGER = logging.getLogger(__name__)


def memo(func):
	"""In memory memoization without persistence."""
	cache = {}
	func.__memo_cache__ = cache
	@wraps(func)
	def wrap(*args):
		if args not in cache:
			return_value = func(*args)
			LOGGER.debug('Saving value "%s" to in memory cache.', return_value)
			cache[args] = return_value
		else:
			return_value = cache[args]
			LOGGER.debug('Serving value "%s" from in memory cache.', return_value)
		return return_value
	return wrap


def memosql(func):
	"""Persistent memoization to an sqlite3 database."""
	self_dir = os.path.abspath(os.path.dirname(__file__))
	db_base = func.__module__ + '.' + func.__name__ + '.db'
	db_path = os.path.join(self_dir, db_base)
	LOGGER.debug('Memoizing "%s.%s" to database "%s".',
							 func.__module__, func.__name__, db_path)
	db = sqlite3.connect(db_path)

	# Create the database table.
	try:
		c = db.cursor()
		c.execute('CREATE TABLE memo (args TEXT, return TEXT)')
		db.commit()
		LOGGER.debug('Created "memo" table in database "%s".', db_base)
	except sqlite3.OperationalError:
		LOGGER.debug('Table "memo" already exists in database "%s".', db_base)

	setattr(func, '__memosql_db_path__', db_path)
	setattr(func, '__memosql_db__', db)
		
	@wraps(func)
	def wrap(*args):
		# Get the args as a 32-byte ASCII hex digest.
		args_pickle = base64.b64encode(pickle.dumps(args))
	
		# Query to see if the value is cached.
		LOGGER.debug('Querying database "%s" for args "%s".', db_base, args)
		c = db.cursor()
		c.execute('SELECT return FROM memo WHERE args=? LIMIT 1', (args_pickle,))
		return_pickle = c.fetchone()
		if return_pickle != None:
			return_value = pickle.loads(base64.b64decode(return_pickle[0]))
			LOGGER.debug('Returning memoized value "%s" from database "%s".',
									 return_value, db_base)
			return return_value
								 
		# The value does not exist in the database, so evaluate the function
		# and save it.
		return_value = func(*args)
		LOGGER.debug('Saving value "%s" to database "%s".',
								 return_value, db_base)
		return_pickle = base64.b64encode(pickle.dumps(return_value))
		c.execute('INSERT INTO memo VALUES (?, ?)', (args_pickle, return_pickle))
		db.commit()
		return return_value

	return wrap


def KillDatabase(func):
	"""Closes and erases the database associated with the wrapped |func|."""
	LOGGER.info('Closing and erasing "%s".', func.__memosql_db_path__)
	func.__memosql_db__.close()
	os.remove(func.__memosql_db_path__)
	

if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)

	# This uses in memory memoization, persisting to a database. 
	@memo
	@memosql
	def fib(i):
		LOGGER.debug('Evaluating fib(%d).', i)
		if i == 0:
			return 0
		elif i == 1 or i == 2:
			return 1
		return fib(i - 2) + fib(i - 1)

	print fib(10)
	print fib(10)

	# Clean up the database.
	KillDatabase(fib)