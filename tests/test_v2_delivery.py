import hashlib
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from publishing_v2.delivery import (
    AmbiguousDeliveryError,
    DeliveryError,
    DeliveryStore,
    TemporaryDeliveryError,
    theme_active,
    theme_expiry,
)


class ThemeWindowTests(unittest.TestCase):
    def test_expiry_is_start_of_third_saudi_calendar_day(self):
        activated = datetime(2026, 9, 12, 22, 30, tzinfo=timezone.utc)
        expiry = theme_expiry(activated)
        self.assertEqual(datetime(2026, 9, 15, 0, 0, tzinfo=ZoneInfo("Asia/Riyadh")), expiry)
        self.assertTrue(theme_active(activated, expiry - timedelta(microseconds=1)))
        self.assertFalse(theme_active(activated, expiry))

    def test_naive_datetimes_are_rejected(self):
        with self.assertRaises(ValueError):
            theme_expiry(datetime(2026, 1, 1))
        with self.assertRaises(ValueError):
            theme_active(datetime.now(timezone.utc), datetime(2026, 1, 1))
        with self.assertRaises(ValueError):
            theme_active(datetime(2026, 1, 1), datetime.now(timezone.utc))


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "delivery.sqlite3"
        self.frames = []
        for index in range(6):
            path = self.root / f"frame-{index}.jpg"
            path.write_bytes(f"frame {index}".encode())
            self.frames.append(path)
        self.now = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)
        self.expires = self.now + timedelta(hours=2)

    def tearDown(self):
        self.temp.cleanup()

    def prepare_story(self, store=None, post_id="post"):
        store = store or DeliveryStore(self.db)
        store.prepare(post_id, "event", self.expires, self.frames, format="story")
        return store

    def test_prepare_stores_hashes_and_rejects_changed_payload(self):
        store = self.prepare_story()
        status = store.status("post")
        self.assertEqual(hashlib.sha256(self.frames[0].read_bytes()).hexdigest(), status["frames"][0]["sha256"])
        store.prepare("post", "event", self.expires, self.frames, format="story")
        with self.assertRaises(DeliveryError):
            store.prepare("post", "different", self.expires, self.frames, format="story")
        self.frames[0].write_bytes(b"changed")
        with self.assertRaises(DeliveryError):
            store.prepare("post", "event", self.expires, self.frames, format="story")

    def test_format_frame_counts_are_enforced(self):
        store = DeliveryStore(self.db)
        with self.assertRaises(ValueError):
            store.prepare("bad", "event", self.expires, self.frames[:2], format="story")
        with self.assertRaises(ValueError):
            store.prepare("bad", "event", self.expires, self.frames[:2], format="info")
        store.prepare("info", "event", self.expires, self.frames[:1], format="info")
        store.prepare("topic", "event", self.expires, self.frames[:1], format="topic")

    def test_restart_preserves_receipts_and_retry_sends_remaining_frames(self):
        store = self.prepare_story()
        first_calls = []

        def first_sender(path, key):
            first_calls.append((path, key))
            if len(first_calls) == 3:
                raise TemporaryDeliveryError("not accepted")
            return f"receipt-{len(first_calls)}"

        self.assertEqual("pending", store.deliver("post", first_sender, self.now)["status"])
        restarted = DeliveryStore(self.db)
        retry_calls = []
        result = restarted.deliver("post", lambda path, key: retry_calls.append(path) or f"retry-{len(retry_calls)}", self.now)
        self.assertEqual("delivered", result["status"])
        self.assertEqual([str(path) for path in self.frames[2:]], retry_calls)
        self.assertEqual(["receipt-1", "receipt-2", "retry-1", "retry-2", "retry-3", "retry-4"], [frame["receipt"] for frame in result["frames"]])

    def test_empty_receipt_and_ambiguous_exception_become_unknown(self):
        for post_id, sender in (
            ("empty", lambda path, key: ""),
            ("ambiguous", lambda path, key: (_ for _ in ()).throw(AmbiguousDeliveryError("maybe accepted"))),
            ("unexpected", lambda path, key: (_ for _ in ()).throw(RuntimeError("socket closed"))),
        ):
            with self.subTest(post_id=post_id):
                store = self.prepare_story(post_id=post_id)
                self.assertEqual("unknown", store.deliver(post_id, sender, self.now)["status"])
                self.assertEqual("unknown", store.status(post_id)["frames"][0]["state"])

    def test_unknown_requires_explicit_proof_to_resolve(self):
        store = self.prepare_story()
        store.deliver("post", lambda path, key: "", self.now)
        for kwargs in ({}, {"receipt": "r", "definitely_not_sent": True}, {"definitely_not_sent": False}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                store.resolve_unknown("post", 0, **kwargs)
        store.resolve_unknown("post", 0, definitely_not_sent=True)
        self.assertEqual("pending", store.status("post")["frames"][0]["state"])

    def test_resolved_receipt_is_never_resent(self):
        store = self.prepare_story()
        store.deliver("post", lambda path, key: "", self.now)
        store.resolve_unknown("post", 0, receipt="external-proof")
        sent = []
        result = store.deliver("post", lambda path, key: sent.append(path) or "receipt", self.now)
        self.assertEqual("delivered", result["status"])
        self.assertNotIn(str(self.frames[0]), sent)
        self.assertEqual("external-proof", result["frames"][0]["receipt"])

    def test_expired_theme_blocks_first_send(self):
        store = self.prepare_story()
        calls = []
        result = store.deliver("post", lambda path, key: calls.append(path) or "r", self.expires)
        self.assertEqual("expired", result["status"])
        self.assertEqual([], calls)

    def test_expiry_during_deck_prevents_later_sends(self):
        store = self.prepare_story()
        times = iter((self.now, self.now, self.expires))
        calls = []
        result = store.deliver("post", lambda path, key: calls.append(path) or "r", lambda: next(times))
        self.assertEqual("expired", result["status"])
        self.assertEqual([str(self.frames[0]), str(self.frames[1])], calls)

    def test_changed_frame_bytes_block_delivery(self):
        store = self.prepare_story()
        self.frames[2].write_bytes(b"mutated")
        calls = []
        result = store.deliver("post", lambda path, key: calls.append(path) or "r", self.now)
        self.assertEqual("artifact_changed", result["status"])
        self.assertEqual([], calls)

    def test_frame_changed_middeck_is_not_sent(self):
        store = self.prepare_story()
        calls = []

        def sender(path, key):
            calls.append(path)
            if len(calls) == 1:
                self.frames[1].write_bytes(b"changed during delivery")
            return "r"

        result = store.deliver("post", sender, self.now)
        self.assertEqual("artifact_changed", result["status"])
        self.assertEqual([str(self.frames[0])], calls)

    def test_delivered_state_without_receipt_is_not_success(self):
        store = self.prepare_story()
        with sqlite3.connect(self.db) as connection:
            connection.execute("UPDATE delivery_frames SET state = 'delivered', receipt = 'r' WHERE post_id = 'post'")
            connection.execute("UPDATE delivery_frames SET receipt = NULL WHERE post_id = 'post' AND frame_index = 2")
            connection.execute("UPDATE delivery_posts SET outcome = 'delivered' WHERE post_id = 'post'")
        self.assertNotEqual("delivered", store.status("post")["status"])

    def test_cached_success_requires_expected_frame_count(self):
        store = self.prepare_story()
        with sqlite3.connect(self.db) as connection:
            connection.execute("UPDATE delivery_frames SET state = 'delivered', receipt = 'r' WHERE post_id = 'post'")
            connection.execute("DELETE FROM delivery_frames WHERE post_id = 'post' AND frame_index = 5")
            connection.execute("UPDATE delivery_posts SET outcome = 'delivered' WHERE post_id = 'post'")
        self.assertEqual("unknown", store.status("post")["status"])

    def test_separate_instances_do_not_reclaim_active_send(self):
        first = self.prepare_story()
        second = DeliveryStore(self.db)
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def blocking_sender(path, key):
            calls.append(path)
            entered.set()
            release.wait(2)
            return "r"

        thread = threading.Thread(target=lambda: first.deliver("post", blocking_sender, self.now))
        thread.start()
        self.assertTrue(entered.wait(1))
        competing_calls = []
        competing = second.deliver("post", lambda path, key: competing_calls.append(path) or "duplicate", self.now)
        self.assertEqual("sending", competing["status"])
        self.assertEqual([], competing_calls)
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(6, len(calls))

    def test_symlink_database_alias_uses_same_post_lock(self):
        first = self.prepare_story()
        alias = self.root / "alias.sqlite3"
        alias.symlink_to(self.db)
        second = DeliveryStore(alias)
        entered = threading.Event()
        release = threading.Event()

        def blocking_sender(path, key):
            entered.set()
            release.wait(2)
            return "r"

        thread = threading.Thread(target=lambda: first.deliver("post", blocking_sender, self.now))
        thread.start()
        self.assertTrue(entered.wait(1))
        competing_calls = []
        result = second.deliver("post", lambda path, key: competing_calls.append(path) or "duplicate", self.now)
        self.assertEqual("sending", result["status"])
        self.assertEqual([], competing_calls)
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())

    def test_datetime_now_advances_with_elapsed_monotonic_time(self):
        store = self.prepare_story()
        calls = []
        with patch("publishing_v2.delivery.monotonic", side_effect=(100.0, 100.0, 7301.0)):
            result = store.deliver("post", lambda path, key: calls.append(path) or "r", self.now)
        self.assertEqual("expired", result["status"])
        self.assertEqual([str(self.frames[0])], calls)

    def test_sender_is_not_called_when_pending_transition_loses_race(self):
        store = self.prepare_story()
        original_read = Path.read_bytes
        reads = 0

        def racing_read(path):
            nonlocal reads
            data = original_read(path)
            reads += 1
            if reads == 7:
                with sqlite3.connect(self.db) as connection:
                    connection.execute(
                        "UPDATE delivery_frames SET state = 'delivered', receipt = 'external' "
                        "WHERE post_id = 'post' AND frame_index = 0"
                    )
            return data

        sender_calls = []
        with patch.object(Path, "read_bytes", racing_read), self.assertRaises(DeliveryError):
            store.deliver("post", lambda path, key: sender_calls.append(path) or "r", self.now)
        self.assertEqual([], sender_calls)

    def test_abandoned_sending_becomes_unknown_on_restart(self):
        store = self.prepare_story()
        with sqlite3.connect(self.db) as connection:
            connection.execute("UPDATE delivery_frames SET state = 'sending' WHERE post_id = 'post' AND frame_index = 0")
        restarted = DeliveryStore(self.db)
        calls = []
        result = restarted.deliver("post", lambda path, key: calls.append(path) or "r", self.now)
        self.assertEqual("unknown", result["status"])
        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
