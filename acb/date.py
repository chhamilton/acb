#!/usr/bin/env python
"""Date utilities."""

import datetime

def AddBusinessDays(date, days):
  # Monday = 0, Sunday = 6
  day = date.weekday()

  business_days = days
  actual_days = 0
  while business_days > 0:
    actual_days += 1
    day = (day + 1) % 7
    if day <= 4:
      business_days -= 1

  return date + datetime.timedelta(days=actual_days)


SETTLE_DAYS = 3
