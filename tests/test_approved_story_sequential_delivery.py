import json
from pathlib import Path

import send_approved_story as sender


def test_send_verified_frames_sequentially_sends_all_six(tmp_path, monkeypatch):
    frames = []
    for index in range(1, 7):
        p = tmp_path / f"frame-{index}.png"
        p.write_bytes(f"frame-{index}".encode())
        frames.append(p)

    calls = []
    monkeypatch.setattr(sender, "_send_document", lambda path, caption="": calls.append((Path(path).name, caption)) or 100 + len(calls))

    ids = sender.send_verified_frames_sequentially(frames, story="Jeddah")

    assert len(calls) == 6
    assert [name for name, _ in calls] == [f"frame-{i}.png" for i in range(1, 7)]
    assert calls[0][1]
    assert all(not caption for _, caption in calls[1:])
    assert len(ids) == 6


def test_send_verified_frames_sequentially_fails_if_any_frame_fails(tmp_path, monkeypatch):
    frames = []
    for index in range(1, 7):
        p = tmp_path / f"frame-{index}.png"
        p.write_bytes(f"frame-{index}".encode())
        frames.append(p)

    count = {"n": 0}
    def fail_on_four(path, caption=""):
        count["n"] += 1
        if count["n"] == 4:
            raise RuntimeError("telegram failed")
        return count["n"]

    monkeypatch.setattr(sender, "_send_document", fail_on_four)

    try:
        sender.send_verified_frames_sequentially(frames, story="Jeddah")
    except RuntimeError as exc:
        assert "telegram failed" in str(exc)
    else:
        raise AssertionError("delivery must fail if any frame is not confirmed")
