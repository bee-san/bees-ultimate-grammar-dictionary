"""Source illustrations for the website and the dictionaries.

絵でわかる日本語's illustrated edition (`edewakaru_v6.zip`) embeds one picture per
post. A contribution names its picture by archive path in
`provenance["illustration"]`; posts that are only a picture (the 自動詞・他動詞
series) are marked `illustrationOnly`.

The archive is a local, locked acquisition, so publication stores every
referenced picture beside the snapshot in two renditions, pinned in
`illustrations.json` by digest. The Pages build verifies those bytes and never
needs the archive:

* `website`: the producer's JPEG, byte for byte (955 pictures, 99.0 MB);
* `dictionary`: AVIF at quality 40 (14.2 MB), packed into both Yomitan ZIPs
  through `with_media`. Furigana stay legible; the loss shows only under
  magnification.
"""

from __future__ import annotations

import concurrent.futures
import copy
import hashlib
import io
import json
import pathlib
import zipfile

CATALOG_NAME = "illustrations.json"
#: Renditions live in this directory beside the snapshot; the website rendition
#: is served at the same path below the site root.
DIRECTORY = "illustrations"
#: Encoder settings per rendition. `jpeg` keeps the producer's bytes. Changing a
#: rendition re-encodes it on the next snapshot.
RENDITIONS = {
    "website": {"format": "jpeg"},
    "dictionary": {"format": "avif", "quality": 40, "speed": 4},
}
_EXTENSIONS = {"avif": ".avif", "webp": ".webp", "jpeg": ".jpeg"}


def illustration_key(point: dict) -> str | None:
    """`<source>:<archive path>` for a contribution's picture, or None."""
    path = (point.get("provenance") or {}).get("illustration")
    return f"{point['source']}:{path}" if isinstance(path, str) and path else None


def is_illustration_only(point: dict) -> bool:
    return bool((point.get("provenance") or {}).get("illustrationOnly"))


def referenced(corpus: dict) -> list[str]:
    """Every picture a contribution names, sorted."""
    keys = {key for entry in corpus["entries"] for point in entry["contributions"]
            if (key := illustration_key(point))}
    return sorted(keys)


def encode(data: bytes, settings: dict) -> bytes:
    """One rendition of a picture. `jpeg` returns the producer's bytes unchanged."""
    if settings["format"] == "jpeg":
        return data
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        image = image.convert("RGB")
        buffer = io.BytesIO()
        if settings["format"] == "avif":
            image.save(buffer, "AVIF", quality=settings["quality"], speed=settings["speed"])
        elif settings["format"] == "webp":
            image.save(buffer, "WEBP", quality=settings["quality"], method=6)
        else:
            raise ValueError(f"unsupported illustration format: {settings['format']}")
        return buffer.getvalue()


def _encode_job(job: tuple[str, str, bytes, dict]) -> tuple[str, str, bytes]:
    key, rendition, data, settings = job
    return key, rendition, encode(data, settings)


def file_name(key: str, settings: dict) -> str:
    """Path of a rendition below `DIRECTORY`: `<source>/<stem><ext>`."""
    source, path = key.split(":", 1)
    stem = pathlib.PurePosixPath(path).stem
    return f"{source}/{stem}{_EXTENSIONS[settings['format']]}"


def _pixel_size(data: bytes) -> tuple[int, int]:
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        return image.size


def build(
    keys: list[str],
    archives: dict[str, bytes],
    output: pathlib.Path,
    *,
    previous: dict | None = None,
    renditions: dict[str, dict] = RENDITIONS,
) -> dict:
    """Write every rendition of every picture in `keys` below `output`; return the catalog.

    `archives` maps a source name to its locked archive bytes. A rendition whose
    source digest and settings match `previous` keeps its committed file, so
    refreshing a snapshot does not re-encode unchanged pictures.
    """
    extensions = [_EXTENSIONS[settings["format"]] for settings in renditions.values()]
    if len(set(extensions)) != len(extensions):
        raise ValueError("each illustration rendition needs its own file format")
    old_settings = (previous or {}).get("renditions", {})
    old_images = (previous or {}).get("images", {})
    opened = {source: zipfile.ZipFile(io.BytesIO(raw)) for source, raw in archives.items()}
    images: dict[str, dict] = {}
    jobs: list[tuple[str, str, bytes, dict]] = []
    for key in keys:
        source, path = key.split(":", 1)
        if source not in opened:
            raise ValueError(f"no locked archive for illustration {key}")
        data = opened[source].read(path)
        digest = hashlib.sha256(data).hexdigest()
        width, height = _pixel_size(data)
        images[key] = {"sourceSha256": digest, "sourceByteCount": len(data), "width": width, "height": height}
        old = old_images.get(key, {})
        for name, settings in renditions.items():
            cached = old.get(name)
            target = output / DIRECTORY / file_name(key, settings)
            if (cached and old_settings.get(name) == settings and old.get("sourceSha256") == digest
                    and target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == cached["sha256"]):
                images[key][name] = cached
            else:
                jobs.append((key, name, data, settings))
    with concurrent.futures.ProcessPoolExecutor() as pool:
        for key, name, encoded in pool.map(_encode_job, jobs, chunksize=4):
            file = file_name(key, renditions[name])
            target = output / DIRECTORY / file
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(encoded)
            images[key][name] = {"file": file, "sha256": hashlib.sha256(encoded).hexdigest(),
                                 "byteCount": len(encoded)}
    expected = {output / DIRECTORY / image[name]["file"] for image in images.values() for name in renditions}
    for stale in (output / DIRECTORY).rglob("*") if (output / DIRECTORY).is_dir() else ():
        if stale.is_file() and stale not in expected:
            stale.unlink()
    return {"schema": 2, "renditions": renditions, "images": {key: images[key] for key in sorted(images)}}


def write_catalog(catalog: dict, output: pathlib.Path) -> bytes:
    raw = (json.dumps(catalog, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode()
    (output / CATALOG_NAME).write_bytes(raw)
    return raw


def load_catalog(directory: pathlib.Path) -> dict:
    """Read the catalog and verify every rendition file it pins."""
    catalog = json.loads((directory / CATALOG_NAME).read_text())
    for key, image in catalog["images"].items():
        for name in catalog["renditions"]:
            entry = image[name]
            relative = pathlib.PurePosixPath(entry["file"])
            if relative.is_absolute() or ".." in relative.parts or str(relative) != entry["file"]:
                raise ValueError(f"Unsafe illustration path: {entry['file']}")
            raw = (directory / DIRECTORY / entry["file"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry["sha256"] or len(raw) != entry["byteCount"]:
                raise ValueError(f"Illustration digest mismatch: {key} ({name})")
    return catalog


def with_media(corpus: dict, images: dict[str, dict]) -> dict:
    """A copy of `corpus` whose contributions name their picture inside the ZIP.

    `images` is a catalog's `images`: each picture's `width`, `height` and
    `dictionary` rendition, packed below `media/`. The bank stage renders
    `illustrationMedia`.
    """
    result = copy.deepcopy(corpus)
    for entry in result["entries"]:
        for point in entry["contributions"]:
            item = images.get(illustration_key(point) or "")
            if item:
                point["provenance"]["illustrationMedia"] = {
                    "path": f"media/{item['dictionary']['file']}", "width": item["width"], "height": item["height"]}
    return result


def require_complete(corpus: dict, catalog: dict) -> None:
    missing = sorted(set(referenced(corpus)) - set(catalog["images"]))
    if missing:
        raise ValueError(f"{len(missing)} illustrations are missing from the catalog, e.g. {missing[:3]}")


__all__ = [
    "CATALOG_NAME",
    "DIRECTORY",
    "RENDITIONS",
    "build",
    "encode",
    "file_name",
    "illustration_key",
    "is_illustration_only",
    "load_catalog",
    "referenced",
    "require_complete",
    "with_media",
    "write_catalog",
]
