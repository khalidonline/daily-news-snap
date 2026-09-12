import unittest
import traceback

from publishing_v2.providers import ProviderError, check_access, generate, search_getty


class RecordingTransport:
    def __init__(self, response=None, error=None):
        self.response = response or {}
        self.error = error
        self.calls = []

    def __call__(self, method, url, headers, payload):
        self.calls.append((method, url, headers, payload))
        if self.error:
            raise self.error
        return self.response


class AccessTests(unittest.TestCase):
    def test_missing_credentials_do_not_make_a_request(self):
        for provider in ("openai", "anthropic", "getty"):
            with self.subTest(provider=provider):
                transport = RecordingTransport()
                result = check_access(provider, {}, transport)
                self.assertEqual("missing_credentials", result["status"])
                self.assertEqual([], transport.calls)

    def test_model_access_uses_provider_specific_endpoint_and_authentication(self):
        cases = (
            ("openai", {"OPENAI_API_KEY": "oa-secret"}, "/v1/models/gpt-6-astra", "Authorization", "Bearer oa-secret"),
            ("anthropic", {"ANTHROPIC_API_KEY": "an-secret"}, "/v1/models/claude-sonnet-5", "x-api-key", "an-secret"),
        )
        for provider, env, path, header, value in cases:
            with self.subTest(provider=provider):
                transport = RecordingTransport({"status_code": 200, "body": {"id": path.rsplit("/", 1)[-1]}})
                result = check_access(provider, env, transport)
                self.assertEqual("available", result["status"])
                method, url, headers, payload = transport.calls[0]
                self.assertEqual(("GET", None), (method, payload))
                self.assertTrue(url.endswith(path))
                self.assertEqual(value, headers[header])

    def test_auth_and_rate_errors_are_safe(self):
        for status_code in (401, 429):
            transport = RecordingTransport({"status_code": status_code, "body": {"error": "oa-secret leaked"}})
            result = check_access("openai", {"OPENAI_API_KEY": "oa-secret"}, transport)
            self.assertEqual("unavailable", result["status"])
            self.assertNotIn("oa-secret", result["detail"])
            self.assertIn(str(status_code), result["detail"])

    def test_transport_exceptions_are_not_exposed(self):
        transport = RecordingTransport(error=RuntimeError("request failed with oa-secret"))
        result = check_access("openai", {"OPENAI_API_KEY": "oa-secret"}, transport)
        self.assertEqual("unavailable", result["status"])
        self.assertNotIn("oa-secret", result["detail"])
        self.assertNotIn("request failed", result["detail"])

    def test_unintegrated_providers_explicitly_require_setup(self):
        for provider in ("reuters", "gcp"):
            result = check_access(provider, {}, RecordingTransport())
            self.assertEqual({"provider": provider, "status": "setup_required", "detail": "End-to-end access has not been configured."}, result)

    def test_malformed_access_response_is_unavailable(self):
        result = check_access("openai", {"OPENAI_API_KEY": "key"}, RecordingTransport({"status_code": 200, "body": []}))
        self.assertEqual("unavailable", result["status"])

    def test_model_access_rejects_wrong_or_empty_model_id(self):
        for model_id in ("", "different-model", "gpt-6-astra-preview"):
            with self.subTest(model_id=model_id):
                result = check_access("openai", {"OPENAI_API_KEY": "key"}, RecordingTransport({"status_code": 200, "body": {"id": model_id}}))
                self.assertEqual("unavailable", result["status"])

    def test_model_access_accepts_date_pinned_alias(self):
        result = check_access("openai", {"OPENAI_API_KEY": "key"}, RecordingTransport({"status_code": 200, "body": {"id": "gpt-6-astra-2026-09-01"}}))
        self.assertEqual("available", result["status"])


class GenerationTests(unittest.TestCase):
    def test_openai_uses_responses_api_and_parses_completed_text(self):
        response = {"status_code": 200, "body": {"id": "resp_1", "status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "draft"}]}], "usage": {"input_tokens": 3, "output_tokens": 2}}}
        transport = RecordingTransport(response)
        result = generate("openai", "write", env={"OPENAI_API_KEY": "key"}, transport=transport, max_output_tokens=120)
        method, url, headers, payload = transport.calls[0]
        self.assertEqual(("POST", "https://api.openai.com/v1/responses"), (method, url))
        self.assertEqual({"model": "gpt-6-astra", "input": "write", "max_output_tokens": 120}, payload)
        self.assertEqual(("gpt-6-astra", "draft", "resp_1"), (result["model"], result["text"], result["response_id"]))
        self.assertEqual(response["body"]["usage"], result["usage"])
        self.assertIsInstance(result["elapsed_ms"], int)

    def test_anthropic_uses_messages_api_and_parses_end_turn(self):
        response = {"status": 200, "body": {"id": "msg_1", "model": "claude-sonnet-5", "stop_reason": "end_turn", "content": [{"type": "text", "text": "copy"}], "usage": {"input_tokens": 2, "output_tokens": 1}}}
        transport = RecordingTransport(response)
        result = generate("anthropic", "write", env={"ANTHROPIC_API_KEY": "key"}, transport=transport)
        method, url, headers, payload = transport.calls[0]
        self.assertEqual(("POST", "https://api.anthropic.com/v1/messages"), (method, url))
        self.assertEqual("claude-sonnet-5", payload["model"])
        self.assertEqual([{"role": "user", "content": "write"}], payload["messages"])
        self.assertEqual("copy", result["text"])

    def test_output_limit_is_validated_before_request(self):
        for limit in (0, 6001, True, 1.5):
            with self.subTest(limit=limit):
                transport = RecordingTransport()
                with self.assertRaises(ValueError):
                    generate("openai", "x", env={"OPENAI_API_KEY": "key"}, transport=transport, max_output_tokens=limit)
                self.assertEqual([], transport.calls)

    def test_missing_generation_credential_does_not_make_a_request(self):
        transport = RecordingTransport()
        with self.assertRaises(ProviderError) as raised:
            generate("openai", "x", env={}, transport=transport)
        self.assertEqual("missing_credentials", raised.exception.code)
        self.assertEqual([], transport.calls)

    def test_incomplete_refused_and_malformed_responses_are_rejected(self):
        bodies = (
            {"id": "x", "status": "incomplete", "output": []},
            {"id": "x", "status": "completed", "output": [{"content": [{"type": "refusal", "refusal": "no"}]}]},
            {"id": "x", "status": "completed", "output": "bad"},
        )
        for body in bodies:
            with self.subTest(body=body):
                with self.assertRaises(ProviderError):
                    generate("openai", "x", env={"OPENAI_API_KEY": "secret"}, transport=RecordingTransport({"status_code": 200, "body": body}))

    def test_http_and_transport_errors_are_sanitized(self):
        transports = (
            RecordingTransport({"status_code": 401, "body": {"error": "secret"}}),
            RecordingTransport(error=RuntimeError("secret")),
        )
        for transport in transports:
            with self.subTest():
                with self.assertRaises(ProviderError) as raised:
                    generate("openai", "x", env={"OPENAI_API_KEY": "secret"}, transport=transport)
                self.assertNotIn("secret", str(raised.exception))

    def test_raw_exception_secret_is_absent_from_formatted_traceback(self):
        transport = RecordingTransport(error=RuntimeError("credential=secret"))
        try:
            generate("openai", "x", env={"OPENAI_API_KEY": "secret"}, transport=transport)
        except ProviderError as error:
            rendered = "".join(traceback.format_exception(error))
        self.assertNotIn("credential=secret", rendered)

    def test_openai_allows_reasoning_item_before_completed_message(self):
        body = {
            "id": "resp_reasoning",
            "status": "completed",
            "output": [
                {"type": "reasoning", "id": "rs_1", "summary": []},
                {"type": "message", "status": "completed", "content": [{"type": "output_text", "text": "answer"}]},
            ],
            "usage": {"input_tokens": 4, "output_tokens": 2},
        }
        result = generate("openai", "x", env={"OPENAI_API_KEY": "key"}, transport=RecordingTransport({"status_code": 200, "body": body}))
        self.assertEqual("answer", result["text"])

    def test_openai_rejects_incomplete_message_and_unsupported_output(self):
        outputs = (
            [{"type": "message", "status": "in_progress", "content": [{"type": "output_text", "text": "partial"}]}],
            [{"type": "unsupported", "content": []}],
            [{"type": "message", "status": "completed", "content": [{"type": "mystery", "text": "x"}]}],
        )
        for output in outputs:
            body = {"id": "resp", "status": "completed", "output": output, "usage": {"input_tokens": 1, "output_tokens": 1}}
            with self.subTest(output=output), self.assertRaises(ProviderError):
                generate("openai", "x", env={"OPENAI_API_KEY": "key"}, transport=RecordingTransport({"status_code": 200, "body": body}))

    def test_generation_requires_nonempty_id_and_valid_usage_counts(self):
        invalid = (
            ("", {"input_tokens": 1, "output_tokens": 1}),
            ("resp", {"input_tokens": -1, "output_tokens": 1}),
            ("resp", {"input_tokens": True, "output_tokens": 1}),
            ("resp", {"input_tokens": 1}),
        )
        for response_id, usage in invalid:
            body = {"id": response_id, "status": "completed", "output": [{"type": "message", "status": "completed", "content": [{"type": "output_text", "text": "x"}]}], "usage": usage}
            with self.subTest(response_id=response_id, usage=usage), self.assertRaises(ProviderError):
                generate("openai", "x", env={"OPENAI_API_KEY": "key"}, transport=RecordingTransport({"status_code": 200, "body": body}))

    def test_anthropic_rejects_malformed_or_unsupported_content_blocks(self):
        for content in ([{"type": "image", "source": {}}], [{"type": "text"}], ["text"]):
            body = {"id": "msg", "stop_reason": "end_turn", "content": content, "usage": {"input_tokens": 1, "output_tokens": 1}}
            with self.subTest(content=content), self.assertRaises(ProviderError):
                generate("anthropic", "x", env={"ANTHROPIC_API_KEY": "key"}, transport=RecordingTransport({"status_code": 200, "body": body}))


class GettyTests(unittest.TestCase):
    def test_editorial_search_returns_metadata_without_licensing_claim(self):
        body = {"images": [{"id": "42", "caption": "Caption", "title": "Title", "date_created": "2026-09-10"}]}
        transport = RecordingTransport({"status_code": 200, "body": body})
        results = search_getty("Saudi event", env={"GETTY_API_KEY": "getty-secret"}, transport=transport, limit=12)
        method, url, headers, payload = transport.calls[0]
        self.assertEqual("GET", method)
        self.assertIn("/v3/search/images/editorial?", url)
        self.assertIn("page_size=10", url)
        self.assertIn("fields=id%2Ctitle%2Ccaption%2Cdate_created", url)
        self.assertNotIn("download_sizes", url)
        self.assertNotIn("getty-secret", url)
        self.assertEqual("getty-secret", headers["Api-Key"])
        self.assertEqual(None, payload)
        self.assertEqual([{"asset_id": "42", "caption": "Caption", "title": "Title", "date_created": "2026-09-10", "download_available": None, "licensing_verified": False}], results)

    def test_getty_missing_key_and_invalid_limit_fail_before_request(self):
        transport = RecordingTransport()
        with self.assertRaises(ProviderError):
            search_getty("query", env={}, transport=transport)
        with self.assertRaises(ValueError):
            search_getty("query", env={"GETTY_API_KEY": "key"}, transport=transport, limit=0)
        self.assertEqual([], transport.calls)


if __name__ == "__main__":
    unittest.main()
