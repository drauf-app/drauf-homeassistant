"""Constants for the drauf integration."""

from datetime import timedelta

DOMAIN = "drauf"

# The plan changes rarely; 5 minutes keeps the kitchen display fresh enough.
UPDATE_INTERVAL = timedelta(minutes=5)

# Window fetched around today. The server caps a range query at 92 days.
PAST_DAYS = 7
FUTURE_DAYS = 60
