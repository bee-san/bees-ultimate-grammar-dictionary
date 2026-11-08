"""Packaging: banks + media -> one reproducible Yomitan ZIP.

Reproducibility rules enforced here:

* fixed member timestamps and permissions, so identical content yields identical
  archive bytes;
* deterministic member order (sorted);
* bank JSON, `index.json`, and `styles.css` at the ZIP root —
  Yomitan requires bank JSON at the root; only media may live in a subfolder.
"""

from __future__ import annotations

import io
import pathlib
import stat
import zipfile

from .jsonio import MalformedPayload, dump_json

#: Fixed ZIP member timestamp (the DOS epoch) for byte-reproducible archives.
ZIP_DATE = (1980, 1, 1, 0, 0, 0)

#: Media members are the only permitted non-root paths.
MEDIA_DIR = "media"


def _member(name: str, data: bytes | str) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(filename=name, date_time=ZIP_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.create_system = 3  # unix
    if isinstance(data, str):
        data = data.encode("utf-8")
    return info, data


def build_zip(members: dict[str, bytes | str]) -> bytes:
    """Pack `members` (member name -> bytes/text) into a reproducible ZIP."""
    for name in members:
        pure = pathlib.PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or pure.is_absolute()
            or ".." in pure.parts
            or "." in pure.parts
            or str(pure) != name
        ):
            raise MalformedPayload(f"unsafe ZIP member name: {name!r}")
        if "/" in name and not name.startswith(f"{MEDIA_DIR}/"):
            raise MalformedPayload(
                f"non-root member outside {MEDIA_DIR}/: {name!r} "
                "(Yomitan requires bank JSON at the ZIP root)"
            )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in sorted(members):
            info, data = _member(name, members[name])
            archive.writestr(info, data)
    return buffer.getvalue()


def referenced_media(node: object) -> set[str]:
    """Archive paths of every image a structured-content tree shows."""
    if isinstance(node, list):
        return set().union(*(referenced_media(child) for child in node)) if node else set()
    if isinstance(node, dict):
        found = {node["path"]} if node.get("tag") == "img" and isinstance(node.get("path"), str) else set()
        return found | referenced_media(node.get("content"))
    return set()


def package_members(
    *,
    index: dict,
    banks: dict[str, list],
    styles_css: str,
    tag_bank: list | None = None,
    media: dict[str, bytes] | None = None,
    extra: dict[str, bytes | str] | None = None,
) -> dict[str, bytes | str]:
    """Assemble the complete member map for the dictionary ZIP.

    Only media some card shows is packed: a picture of a sense past the popup's
    per-source budget is reachable on the website, not in the archive. A card
    naming media that was not supplied fails closed.
    """
    members: dict[str, bytes | str] = {
        "index.json": dump_json(index),
        "styles.css": styles_css,
    }
    for name, bank in banks.items():
        members[name] = dump_json(bank)
    if tag_bank:
        members["tag_bank_1.json"] = dump_json(tag_bank)
    # Malformed banks are the validation gate's to reject, not this scan's.
    shown = {path for bank in banks.values() if isinstance(bank, list) for row in bank
             if isinstance(row, list) and len(row) > 5 for path in referenced_media(row[5])}
    supplied = {f"{MEDIA_DIR}/{name}": payload for name, payload in (media or {}).items()}
    missing = sorted(shown - set(supplied))
    if missing:
        raise MalformedPayload(f"cards show media that was not packed: {missing[:3]}")
    members.update((path, supplied[path]) for path in sorted(shown))
    members.update(extra or {})
    return members


__all__ = ["ZIP_DATE", "MEDIA_DIR", "build_zip", "package_members", "referenced_media"]
