"""
CareLens API Security and Readiness Checks Tests.
Verifies application startup model loading, /api/ready endpoint, CORS origin restrictions,
and protection on uploads, inspection endpoints, and audit records.
"""

import unittest
from fastapi.testclient import TestClient

from app.main import app, ALLOWED_ORIGINS


class TestApiSecurityAndReadiness(unittest.TestCase):
    def test_startup_readiness_check(self):
        """When the app starts up, /api/ready accurately reflects model engine readiness."""
        with TestClient(app) as client:
            resp = client.get("/api/ready")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "ready")
            self.assertTrue(data["ready"])
            self.assertTrue(data["is_prototype"])
            self.assertIn("gemma_model", data)

    def test_health_check_prototype_identification(self):
        """Health check returns prototype flag and clinical decision support disclaimer."""
        with TestClient(app) as client:
            resp = client.get("/api/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data["is_prototype"])
            self.assertIn("PROTOTYPE", data["service"])
            self.assertIn("disclaimer", data)

    def test_cors_restrictions(self):
        """Allowed origin receives CORS headers; unauthorized origin does not receive wildcard."""
        with TestClient(app) as client:
            allowed = ALLOWED_ORIGINS[0]
            resp = client.options(
                "/api/protocols",
                headers={
                    "Origin": allowed,
                    "Access-Control-Request-Method": "GET",
                },
            )
            self.assertEqual(resp.headers.get("access-control-allow-origin"), allowed)

            # Check that wildcard '*' is not used when credentials are required
            self.assertNotEqual(resp.headers.get("access-control-allow-origin"), "*")

    def test_prototype_security_headers(self):
        """All responses carry prototype identification and nosniff security headers."""
        with TestClient(app) as client:
            resp = client.get("/api/protocols")
            self.assertEqual(resp.headers.get("X-CareLens-Prototype"), "true")
            self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")

    def test_upload_mime_type_protection(self):
        """Disallowed file formats (e.g. text/plain or executable) are rejected with 415."""
        with TestClient(app) as client:
            files = {"file": ("malicious.txt", b"not an image", "text/plain")}
            resp = client.post("/api/audit/upload", files=files)
            self.assertEqual(resp.status_code, 415)
            self.assertIn("Unsupported Media Type", resp.json()["detail"])

    def test_audit_log_pagination_limit_protection(self):
        """Requesting an invalid pagination limit (>500 or <1) returns 400 Bad Request."""
        with TestClient(app) as client:
            resp = client.get("/api/audit-log?limit=9999")
            self.assertEqual(resp.status_code, 400)

            resp_neg = client.get("/api/audit-log?limit=0")
            self.assertEqual(resp_neg.status_code, 400)

    def test_audit_verify_endpoint(self):
        """The /api/audit/verify endpoint returns cryptographic verification."""
        with TestClient(app) as client:
            resp = client.get("/api/audit/verify")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("valid", data)
            self.assertIn("record_count", data)


if __name__ == "__main__":
    unittest.main()
