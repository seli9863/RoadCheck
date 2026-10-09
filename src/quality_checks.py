"""
Data quality checks for silver layer.
- Flag dark/blank/corrupt images
- Warn on stale cameras (no new image in 1 hour)
- Warn on API feeds returning 0 features or repeated failures
"""
# TODO Saturday
