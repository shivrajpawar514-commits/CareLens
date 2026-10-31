"""
CareLens Master Automated Test Suite Runner.
Executes schema, protocol boundaries, safety & uncertainty policies, image preprocessor,
cryptographic audit integrity, and API readiness/security test suites.
"""

import os
import sys
import unittest

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.schema.test_schema import TestCareLensSchema
from tests.protocols.test_protocols import TestProtocolEngine
from tests.protocols.test_threshold_boundaries import TestProtocolThresholdBoundaries
from tests.safety.test_safety_escalation import TestSafetyEscalation
from tests.safety.test_uncertainty_and_abstention import TestUncertaintyAndAbstention
from tests.images.test_preprocessor import TestImagePreprocessor
from tests.audit.test_audit_integrity import TestAuditIntegrity
from tests.api.test_api_security_readiness import TestApiSecurityAndReadiness


def run_all():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    suite.addTests(loader.loadTestsFromTestCase(TestCareLensSchema))
    suite.addTests(loader.loadTestsFromTestCase(TestProtocolEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestProtocolThresholdBoundaries))
    suite.addTests(loader.loadTestsFromTestCase(TestSafetyEscalation))
    suite.addTests(loader.loadTestsFromTestCase(TestUncertaintyAndAbstention))
    suite.addTests(loader.loadTestsFromTestCase(TestImagePreprocessor))
    suite.addTests(loader.loadTestsFromTestCase(TestAuditIntegrity))
    suite.addTests(loader.loadTestsFromTestCase(TestApiSecurityAndReadiness))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    run_all()
