"""Implementations of the loading stages a category can declare.

Split by which side of ``StageId.PARSE`` they run on: ``raw`` operates on JSON
objects, ``typed`` on ``TestEntry`` objects.
"""
