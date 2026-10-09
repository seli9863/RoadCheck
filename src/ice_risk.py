"""
Rule-based ice-risk forecast per camera.

Rules:
  HIGH   : condition is wet or snow_ice AND surface/air temp <= 0°C
  MEDIUM : condition is wet AND temp between 0°C and 3°C
  LOW    : everything else
"""
# TODO Monday
