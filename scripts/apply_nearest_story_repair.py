from pathlib import Path

path = Path("story_runtime.py")
text = path.read_text(encoding="utf-8")
if "def curated_frame_visual_filename(" in text:
    raise SystemExit("repair already applied")

text = text.replace("import os\n", "import os\nimport shutil\n", 1)
needle = "story_editorial_runtime.configure(sb)\ncity_visual_v3.configure(sb)\n\n"
insert = '''story_editorial_runtime.configure(sb)
city_visual_v3.configure(sb)

# Exact story+frame repairs. These do not broaden global relevance: each pin
# is a previously reviewed local asset assigned to one specific narrative beat.
_CURATED_FRAME_VISUALS = {
    "قصة تأسيس مؤسسة النقد ساما": (
        (("نقود من فضة", "فضة فقط"), "silver-riyal.png"),
        (("ورقة صُنعت لأجل الحجاج", "إيصال الحج"), "first-hajj-receipt.png"),
        (("من إيصال إلى احتياطي",), "sama-history-hq.jpg"),
        (("سعر لا يتحرك", "3.75"), "targeted-riyal-five-faisal-museum.jpg"),
    ),
    "قصة أول مطار في جدة وتطور الطيران المدني": (
        (("الحج كان يأتي من البحر",), "jeddah-port.jpg"),
        (("طائرة واحدة على مدرج تراب",), "saudia-dc3-crowd.jpg"),
        (("نهاية المطار الأول",), "saudia-707-historic.jpg"),
    ),
}


def curated_frame_visual_filename(story, frame):
    blob = " ".join(
        str((frame or {}).get(key, "") or "")
        for key in ("heading", "text", "punch")
    )
    for markers, filename in _CURATED_FRAME_VISUALS.get(str(story or "").strip(), ()):
        if any(marker and marker in blob for marker in markers):
            return filename
    return None


_pre_curated_find_photo = sb.find_photo


def _find_photo_with_curated_frame_pin(
    spec, out_path, seen=(), context="", allow_neutral=True, bank=None
):
    filename = curated_frame_visual_filename(
        sb.STORY, spec if isinstance(spec, dict) else {}
    )
    if filename:
        source = Path("images") / filename
        if source.exists() and source.is_file():
            try:
                digest = sb._photo_digest(source)
                duplicate = any(sb.same_picture(digest, prior) for prior in seen)
            except Exception:
                duplicate = False
            if not duplicate:
                out = Path(out_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, out)
                print(f"      curated frame pin: {filename}")
                return str(out)
            print(f"      curated frame pin already used: {filename}")
    return _pre_curated_find_photo(
        spec, out_path, seen, context,
        allow_neutral=allow_neutral, bank=bank,
    )


sb.find_photo = _find_photo_with_curated_frame_pin

'''
if needle not in text:
    raise SystemExit("insertion point not found")
text = text.replace(needle, insert, 1)
path.write_text(text, encoding="utf-8")
