"""Pytest configuration for this repo.

The `tests/` folder contains a mix of:
- pytest-style unit tests (safe to collect)
- standalone script-style validation scripts (run on import, may hit network/DB)

To keep `pytest` stable and fast, we explicitly ignore script-style files.
They can still be run manually via `python tests/<script>.py`.
"""

collect_ignore = [
    'test_bugfixes.py',
    'test_data_fixes.py',
    'test_data_source_consistency.py',
    'test_pagination.py',
    'test_sector_api.py',
]
