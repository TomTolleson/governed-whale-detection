"""List SanctSound Stellwagen Bank deployments (audio + humpback labels).

Uses anonymous gcsfs `ls` calls on one folder at a time (no recursive scans of
whole sites). Writes a JSON summary to the path given on the command line.

    python -m src.inventory data/inventory.json
"""

import json
import sys
import warnings
from collections import Counter
from pathlib import PurePosixPath

import gcsfs

warnings.filterwarnings("ignore", category=FutureWarning)

BUCKET = "noaa-passive-bioacoustic/sanctsound"
SITES = ["sb01", "sb02", "sb03"]


def summarize_files(fs, prefix):
    """Return file count, size, extensions and a sample for one folder (non-recursive)."""
    try:
        entries = fs.ls(prefix, detail=True)
    except FileNotFoundError:
        return None
    files = [e for e in entries if e["type"] == "file"]
    subdirs = [e["name"].rsplit("/", 1)[-1] for e in entries if e["type"] == "directory"]
    exts = Counter(PurePosixPath(f["name"]).suffix.lower() or "(none)" for f in files)
    sample = files[0] if files else None
    return {
        "prefix": prefix,
        "file_count": len(files),
        "total_bytes": sum(int(f.get("size") or 0) for f in files),
        "extensions": dict(exts),
        "subdirs": subdirs,
        "sample_name": sample["name"].rsplit("/", 1)[-1] if sample else None,
        "sample_bytes": int(sample["size"]) if sample else None,
    }


def main(out_path):
    fs = gcsfs.GCSFileSystem(token="anon")
    result = {}
    for site in SITES:
        deployments = sorted(p.rsplit("/", 1)[-1] for p in fs.ls(f"{BUCKET}/audio/{site}"))
        label_dirs = {p.rsplit("/", 1)[-1] for p in fs.ls(f"{BUCKET}/products/detections/{site}")}
        rows = []
        for dep in deployments:
            hb = f"{dep}_humpbackwhale_1d"
            rows.append({
                "deployment": dep,
                "audio": summarize_files(fs, f"{BUCKET}/audio/{site}/{dep}/audio"),
                "labels": summarize_files(fs, f"{BUCKET}/products/detections/{site}/{hb}/data")
                if hb in label_dirs else None,
            })
            print(site, dep, flush=True)
        result[site] = rows
    with open(out_path, "w") as f:
        json.dump(result, f, indent=1)


def render_table(inv):
    """Return a Markdown table (one row per deployment) from the JSON summary."""
    out = ["| Site | Dep | Audio | Files | GB | Ext | Sample file | Sample MB | Humpback 1d labels | Label files |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for site, rows in inv.items():
        for r in rows:
            a, lab = r["audio"], r["labels"]
            dep = r["deployment"].rsplit("_", 1)[-1]
            if a:
                ext = ", ".join(f"{k}×{v}" for k, v in a["extensions"].items())
                acols = f"yes | {a['file_count']} | {a['total_bytes'] / 1e9:.1f} | {ext} | `{a['sample_name']}` | {a['sample_bytes'] / 1e6:.0f}"
            else:
                acols = "no | – | – | – | – | –"
            lcols = (f"yes | {', '.join(f'{k}×{v}' for k, v in lab['extensions'].items())}"
                     if lab else "**no** | –")
            out.append(f"| {site} | {dep} | {acols} | {lcols} |")
    return "\n".join(out)


if __name__ == "__main__":
    main(sys.argv[1])
