"""Trusted fixed pytest entrypoint; a zero exit without this report is not a pass.

The marker catches interrupted/empty/skipped runs. This is not a hostile-code
anti-cheating oracle: Python under test shares a process with its test runner.
"""
import json
import sys
import pytest


class Results:
    def __init__(self):
        self.collected = self.passed = self.failed = self.skipped = self.errors = 0

    def pytest_collection_finish(self, session):
        self.collected = len(session.items)

    def pytest_runtest_logreport(self, report):
        if report.skipped:
            self.skipped += 1
        elif report.failed:
            if report.when == 'call':
                self.failed += 1
            else:
                self.errors += 1
        elif report.when == 'call' and report.passed:
            self.passed += 1


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) == 2 else ''
    if target not in {'/workspace/tests/test_public.py', '/judge/test_acceptance.py'}:
        raise SystemExit(2)
    results = Results()
    code = pytest.main(['-q', '--tb=short', '--disable-warnings', '--color=no', '-p', 'no:cacheprovider',
                        '-c', '/dev/null', '--rootdir=/workspace', '-o', 'pythonpath=/workspace/src', target], plugins=[results])
    print('\nREPOMIND_RESULT ' + json.dumps({'exit_code': int(code), **vars(results)}, sort_keys=True), flush=True)
    raise SystemExit(code)
