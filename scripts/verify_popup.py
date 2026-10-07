#!/usr/bin/env python3
"""Check real Japanese hover/deinflection queries against both packaged ZIPs."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES = [
    ("これは便利です。", "は", "は", "IMABI"),
    ("政治について話す。", "について", "について", "IMABI"),
    ("失敗するにちがいない。", "にちがいない", "にちがいない", "IMABI"),
    ("食べすぎた。", "すぎた", "すぎる", "IMABI"),
    ("食べてしまった。", "てしまった", "てしまう", "IMABI"),
    ("歩きにくかった。", "にくかった", "にくい", "IMABI"),
    ("飛び込んだ。", "込んだ", "込む", "IMABI"),
    ("行かざるを得なかった。", "ざる", "ざるを得ない", "IMABI"),
    ("戻ってこなかった。", "てこなかった", "てくる", "IMABI"),
    ("毎日読むことにした。", "ことにした", "ことにする", "IMABI"),
    ("学生らしかった。", "らしかった", "らしい", "Bunpro Grammar Reference"),
    ("働きながら勉強する。", "ながら", "ながら", "Bunpro Grammar Reference"),
    ("読めば読むほど分かる。", "ほど", "ほど", "Bunpro Grammar Reference"),
    ("行かないで。", "ないで", "ないで", "Bunpro Grammar Reference"),
    ("学生あっての大学だ。", "あっての", "あっての", "日本語文型辞典"),
    ("あいにく雨です。", "あいにく", "あいにく", "絵でわかる日本語"),
    # Records filed under a typo or a corrupted headword are found by their real form.
    ("学生とはいえ、", "とはいえ", "とはいえ", "どんなときどう使う 日本語表現文型辞典"),
    ("天才と言っても過言ではない。", "と言っても", "と言っても過言ではない", "NINJAL 日本語文型データベース"),
    ("笑わずにはいられなかった。", "ずには", "ずにはいられない", "どんなときどう使う 日本語表現文型辞典"),
    # Kanji headwords are also found by a kana spelling of their reading.
    ("雨だ。そのうえ風も強い。", "そのうえ", "その上", "DoJG 日本語文法辞典(全集)"),
    ("いつのまにか寝ていた。", "いつのまにか", "いつの間にか", "Bunpro Grammar Reference"),
]
# Synthetic lemmas a producer filed negative constructions under must not be
# offered as the headword of a real negative (`ずにはいられなかった` is not `ずにはいる`).
ABSENT = [
    ("笑わずにはいられなかった。", "ずには", "ずにはいる"),
    ("笑わずにはいられなかった。", "ずには", "ずにはいられる"),
    ("読みもしない。", "もしない", "もする"),
    ("急がねばならない。", "ねば", "ねばなる"),
    # A counter whose reading spells a particle is not offered for the particle.
    ("これは何ですか。", "か。", "化"),
    ("行くわ。", "わ", "羽"),
]


def source_names(node: object) -> set[str]:
    if isinstance(node, list):
        return set().union(*(source_names(child) for child in node))
    if isinstance(node, dict):
        if "sourceName" in node.get("data", {}):
            return {node["content"]}
        return source_names(node.get("content"))
    return set()


def verify(path: pathlib.Path) -> dict:
    vendor = ROOT / "tests/vendor/yomitan"
    for name, metadata in json.loads((vendor / "SOURCE.lock.json").read_text())["files"].items():
        raw = (vendor / name).read_bytes()
        if len(raw) != metadata["byteCount"] or hashlib.sha256(raw).hexdigest() != metadata["sha256"]:
            raise ValueError(f"Pinned Yomitan engine digest mismatch: {name}")
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js is required for the Yomitan popup integration check")
    wanted = {case[2] for case in CASES + ABSENT}
    rows = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if re.fullmatch(r"term_bank_\d+\.json", name):
                for row in json.loads(archive.read(name)):
                    if row[0] in wanted:
                        rows.append({"term": row[0], "reading": row[1], "rules": row[3],
                                     "sources": sorted(source_names(row[5]))})
    cases = [dict(zip(("text", "hover", "term", "source"), case)) for case in CASES]
    absent = [dict(zip(("text", "hover", "term"), case)) for case in ABSENT]
    result = subprocess.run([node, str(ROOT / "scripts/verify_popup.mjs")],
                            input=json.dumps({"rows": rows, "cases": cases, "absent": absent}), text=True,
                            capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return {"asset": path.name, **json.loads(result.stdout)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--downloads", type=pathlib.Path, default=pathlib.Path("build/site/downloads"))
    args = parser.parse_args()
    for filename in ("bees-ultimate-grammar-dictionary.zip", "bees-ultimate-grammar-dictionary-en.zip"):
        print(json.dumps(verify(args.downloads / filename)))
