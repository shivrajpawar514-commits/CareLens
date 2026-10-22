"""
CareLens Comprehensive Test Suite Runner.
Executes schema, protocol, safety, and image processing test suites.
"""

import os
import sys
import unittest

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.schema.test_schema import TestCareLensSchema
from tests.protocols.test_protocols import TestProtocolEngine
from tests.safety.test_safety_escalation import TestSafetyEscalation
from tests.images.test_preprocessor import TestImagePreprocessor


def run_all():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    suite.addTests(loader.loadTestsFromTestCase(TestCareLensSchema))
    suite.addTests(loader.loadTestsFromTestCase(TestProtocolEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestSafetyEscalation))
    suite.addTests(loader.loadTestsFromTestCase(TestImagePreprocessor))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    run_all()
