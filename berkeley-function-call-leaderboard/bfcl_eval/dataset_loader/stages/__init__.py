"""Implementations of the loading stages a category can declare.

Split by which side of ``StageId.PARSE_ENTRIES`` they run on: ``raw`` operates on JSON
objects, ``typed`` on ``TestEntry`` objects.
"""
