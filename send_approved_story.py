#!/usr/bin/env python3
"""Send a human-approved frozen Story artifact to Telegram without rerendering."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
import urllib.request
import uuid
from pathlib import Path

import ready_story_publish as rsp


def _multipart(fields, file_field, file_path):
    boundary = f"----daily-news-snap-{uuid.uuid4().hex}"
    chunks = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'.encode()
    )
    chunks.append(f"Content-Type: {mime}\r\n\r\n".encode())
    chunks.append(file_path.read_bytes())
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _send_document(path: Path, caption: str = "") -> int:
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Telegram credentials are missing")
    fields = {"chat_id": chat_id}
    if caption:
        fields["caption"] = caption
    body, content_type = _multipart(fields, "document", Path(path))
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendDocument",
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    last_error = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                payload = json.loads(resp.read())
            if not payload.get("ok"):
                raise RuntimeError(f"Telegram rejected frame: {payload}")
            return int(payload["result"]["message_id"])
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Telegram frame delivery failed after 3 attempts: {last_error}")


def _multipart_album(fields, frames):
    boundary = f"----daily-news-snap-{uuid.uuid4().hex}"
    chunks = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    for index, frame in enumerate(frames, start=1):
        field = f"frame{index}"
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            f'Content-Disposition: form-data; name="{field}"; filename="{index:02d}-{frame.name}"\r\n'.encode()
        )
        chunks.append(b"Content-Type: image/png\r\n\r\n")
        chunks.append(frame.read_bytes())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _send_document_album(frames, caption: str = "") -> list[int]:
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Telegram credentials are missing")
    frames = [Path(frame) for frame in frames]
    media = []
    for index in range(1, len(frames) + 1):
        item = {"type": "document", "media": f"attach://frame{index}"}
        if index == 1 and caption:
            item["caption"] = caption
        media.append(item)
    body, content_type = _multipart_album(
        {"chat_id": chat_id, "media": json.dumps(media, ensure_ascii=False)},
        frames,
    )
    last_error = None
    for attempt in range(1, 4):
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMediaGroup",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read())
            if not payload.get("ok"):
                raise RuntimeError(f"Telegram rejected album: {payload}")
            message_ids = [int(item["message_id"]) for item in payload.get("result", [])]
            if len(message_ids) != len(frames):
                raise RuntimeError(
                    f"Telegram confirmed {len(message_ids)} of {len(frames)} album frames"
                )
            return message_ids
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Telegram album delivery failed after 3 attempts: {last_error}")


def send_verified_frames_sequentially(frames, *, story: str):
    frames = [Path(p) for p in frames]
    if len(frames) != 6:
        raise RuntimeError(f"approved Story must contain exactly 6 frames, got {len(frames)}")
    message_ids = []
    for index, frame in enumerate(frames, start=1):
        caption = f"[APPROVED] {story}\nFrame {index}/6" if index == 1 else ""
        message_id = _send_document(frame, caption=caption)
        message_ids.append(message_id)
        print(f"    Telegram approved frame {index}/6 confirmed: message_id={message_id}")
    return message_ids


def send_verified_frames_as_document_album(frames, *, story: str):
    frames = [Path(p) for p in frames]
    if len(frames) != 6:
        raise RuntimeError(f"approved Story must contain exactly 6 frames, got {len(frames)}")
    message_ids = _send_document_album(
        frames,
        caption=f"[APPROVED] {story}\n6 frames",
    )
    print(f"    Telegram approved document album confirmed: {len(message_ids)}/6")
    return message_ids


def send_verified_frames_like_riyadh(frames, *, story: str, status: str = "READY"):
    frames = [Path(p) for p in frames]
    if len(frames) != 6:
        raise RuntimeError(f"approved Story must contain exactly 6 frames, got {len(frames)}")
    confirmed = rsp.sb.notify_album(
        f"[{status}] {story}\nFinal publication candidate",
        frames,
        as_documents=True,
    )
    if confirmed is not True:
        raise RuntimeError("Telegram did not confirm the Riyadh-format document album")
    print("    Telegram Riyadh-format document album confirmed: 6/6")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    frames = rsp.verify_review_manifest(manifest, args.manifest.parent)
    send_verified_frames_like_riyadh(
        frames,
        story=manifest["story"],
        status=manifest.get("status", "READY"),
    )
    print(f"APPROVED_STORY_SENT_RIYADH_FORMAT_6_OF_6: {args.manifest}")


if __name__ == "__main__":
    main()
