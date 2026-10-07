#!/usr/bin/env python3
"""Report source-record findability from the committed publication snapshot."""
from __future__ import annotations

import argparse
import json
import pathlib

from build_site import snapshot_inputs
from bugd.popup_lookup import identity, is_japanese_form, load_overrides, lookup_plan
from bugd.website import grouped_entries


def audit(snapshot: pathlib.Path) -> dict:
    corpus, _, revision = snapshot_inputs(snapshot)
    plan = lookup_plan(corpus, load_overrides(snapshot / "popup-overrides.json"))
    reachable = {form: {identity(p) for p in entry["contributions"]}
                 for form, entry in grouped_entries(corpus).items() if is_japanese_form(form)}
    missing = []
    by_source = {s: {"records": 0, "japaneseLookupRecords": 0} for s in sorted(corpus["sourceLabels"])}
    for key, item in plan.items():
        by_source[key[0]]["records"] += 1
        if item["forms"] and all(key in reachable.get(form, set()) for form in item["forms"]):
            by_source[key[0]]["japaneseLookupRecords"] += 1
        else:
            missing.append(key)
    result = {"revision": revision, "sourceRecords": len(plan),
              "japaneseHeadwords": len(reachable), "lookupLinks": sum(len(p["forms"]) for p in plan.values()),
              "sources": by_source, "missing": missing}
    if missing:
        raise ValueError(f"Unreachable source records: {missing}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=pathlib.Path, default=pathlib.Path("website/data"))
    args = parser.parse_args()
    print(json.dumps(audit(args.snapshot), indent=2))
