import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock
from urllib.error import HTTPError


class PermissionAuditTests(unittest.TestCase):
    def _response(self, payload):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        response.__exit__.return_value = False
        return response

    def test_empty_permissions_are_reported_missing(self):
        from publishing_v2 import cloud_permissions

        with mock.patch.object(cloud_permissions, "urlopen", return_value=self._response({"permissions": []})):
            report = cloud_permissions.audit("access-token")

        self.assertEqual(report["status"], "missing_permissions")
        self.assertEqual(report["granted"], [])
        self.assertEqual(report["missing"], list(cloud_permissions.REQUIRED_PERMISSIONS))

    def test_omitted_empty_permissions_are_reported_missing(self):
        from publishing_v2 import cloud_permissions

        with mock.patch.object(cloud_permissions, "urlopen", return_value=self._response({})):
            report = cloud_permissions.audit("access-token")

        self.assertEqual(report["status"], "missing_permissions")
        self.assertEqual(report["missing"], list(cloud_permissions.REQUIRED_PERMISSIONS))

    def test_full_permission_response_passes(self):
        from publishing_v2 import cloud_permissions

        payload = {"permissions": list(cloud_permissions.REQUIRED_PERMISSIONS)}
        with mock.patch.object(cloud_permissions, "urlopen", return_value=self._response(payload)):
            report = cloud_permissions.audit("access-token")

        self.assertEqual(report, {
            "status": "permissions_granted",
            "granted": list(cloud_permissions.REQUIRED_PERMISSIONS),
            "missing": [],
        })

    def test_malformed_response_is_a_safe_error(self):
        from publishing_v2 import cloud_permissions

        malformed = ({"unexpected": []}, {"permissions": "not-a-list"}, {"permissions": [3]})
        for payload in malformed:
            with self.subTest(payload=payload):
                with mock.patch.object(cloud_permissions, "urlopen", return_value=self._response(payload)):
                    self.assertEqual(cloud_permissions.audit("access-token"), {
                        "status": "malformed_response", "granted": [], "missing": []
                    })

    def test_invalid_json_is_a_malformed_response(self):
        from publishing_v2 import cloud_permissions

        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"not-json"
        response.__exit__.return_value = False
        with mock.patch.object(cloud_permissions, "urlopen", return_value=response):
            report = cloud_permissions.audit("access-token")
        self.assertEqual(report, {"status": "malformed_response", "granted": [], "missing": []})

    def test_request_uses_fixed_endpoint_authentication_and_timeout(self):
        from publishing_v2 import cloud_permissions

        captured = {}
        def open_request(request, *, timeout):
            captured.update(request=request, timeout=timeout)
            return self._response({"permissions": []})

        with mock.patch.object(cloud_permissions, "urlopen", side_effect=open_request):
            cloud_permissions.audit("specific-token")

        request = captured["request"]
        self.assertEqual(request.full_url, cloud_permissions.ENDPOINT)
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.headers["Authorization"], "Bearer specific-token")
        self.assertEqual(captured["timeout"], 20)
        self.assertEqual(json.loads(request.data), {
            "permissions": list(cloud_permissions.REQUIRED_PERMISSIONS)
        })

    def test_http_and_transport_exceptions_never_expose_secret(self):
        from publishing_v2 import cloud_permissions

        sentinel = "SENTINEL-CLOUD-TOKEN"
        errors = (
            HTTPError(cloud_permissions.ENDPOINT, 403, sentinel, {}, io.BytesIO(sentinel.encode())),
            RuntimeError(sentinel),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with mock.patch.object(cloud_permissions, "urlopen", side_effect=error):
                    report = cloud_permissions.audit(sentinel)
                encoded = json.dumps(report)
                self.assertNotIn(sentinel, encoded)


class SmokeEntrypointTests(unittest.TestCase):
    def test_smoke_calls_only_offline_and_emits_full_safe_report(self):
        from publishing_v2 import cloud_smoke

        report = {
            "mode": "offline", "status": "offline_ready",
            "editorial_approved": False, "visual_approved": False,
            "licensing_verified": False, "production_deployed": False,
        }
        output = io.StringIO()
        with mock.patch.object(cloud_smoke.evaluate, "run", return_value=report) as run:
            with redirect_stdout(output):
                result = cloud_smoke.main([])

        self.assertEqual(result, 0)
        args, kwargs = run.call_args
        self.assertEqual(args[0], "offline")
        self.assertEqual(kwargs, {"env": {}})
        self.assertTrue(str(args[1]).startswith("/tmp/"))
        emitted = json.loads(output.getvalue())
        self.assertEqual(emitted, report)
        self.assertFalse(any(emitted[key] for key in (
            "editorial_approved", "visual_approved", "licensing_verified", "production_deployed"
        )))

    def test_smoke_rejects_cli_arguments_without_running(self):
        from publishing_v2 import cloud_smoke

        with mock.patch.object(cloud_smoke.evaluate, "run") as run:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cloud_smoke.main(["--allow-paid"]), 2)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
