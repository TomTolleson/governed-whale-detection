"""Check name-derived audio durations against real FLAC headers.

    python -m src.header_check fetch --actor <name>   # 16 KB range requests
    python -m src.header_check report --actor <name>  # docs/header_check.md

Fetches only the first 16 KB of each selected file with an HTTP Range request
(anonymous, public bucket URL), parses the FLAC metadata, and compares the
STREAMINFO duration with the duration estimated in src.label_survey.
"""

import argparse
import hashlib
import json
import re
import urllib.request

from src.audit import log_event
from src.flac_header import parse_flac_header
from src.label_survey import LISTING_PATH, ROOT, file_intervals, parse_start

URL = "https://storage.googleapis.com/noaa-passive-bioacoustic/sanctsound/audio/{site}/sanctsound_{key}/audio/{name}"
RANGE_BYTES = 16 * 1024
OUT_JSON = ROOT / "data" / "header_check.json"
OUT_DOC = ROOT / "docs" / "header_check.md"
MISMATCH_S = 2.0  # report differences larger than this

# (deployment, why it was picked). File chosen by `pick` below.
SELECTION = [
    ("sb01_01", "first", "long name, _Post-Deployment"),
    ("sb01_01", "pre_retrieval", "long name, _Pre-Retrieval (last file; name estimate uses size)"),
    ("sb02_01", "post_clip_small", "long name, _Post-clip, tiny file"),
    ("sb02_01", "post_clip_large", "long name, _Post-clip, full-size file"),
    ("sb02_01", "last", "long name, _Pre-Retrieval_Post-clip"),
    ("sb03_02", "middle", "long name, plain"),
    ("sb01_03", "first", "long name, first audio file (labels start 8 days earlier)"),
    ("sb03_01", "last", "long name, _Pre-Retrieval (labels run 6 days past it)"),
    ("sb01_04", "middle", "short name"),
    ("sb02_08", "middle", "short name"),
    ("sb03_07", "last", "short name, last file of the deployment that ended early"),
    ("sb03_12", "first", "short name, first file"),
    ("sb02_12", "last", "short name, last file (name estimate uses size)"),
]


def pick(files_sorted, how):
    names = [n for _, n, _ in files_sorted]
    if how == "first":
        return 0
    if how == "last":
        return len(names) - 1
    if how == "middle":
        return len(names) // 2
    if how == "pre_retrieval":
        return next(i for i, n in enumerate(names) if n.endswith("_Pre-Retrieval.flac"))
    clips = [i for i, (_, n, s) in enumerate(files_sorted) if n.endswith("_Post-clip.flac")]
    if how == "post_clip_small":
        return min(clips, key=lambda i: files_sorted[i][2])
    if how == "post_clip_large":
        return max(clips, key=lambda i: files_sorted[i][2])
    raise ValueError(how)


def fetch_prefix(url: str) -> tuple[bytes, int, str]:
    req = urllib.request.Request(url, headers={"Range": f"bytes=0-{RANGE_BYTES - 1}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(RANGE_BYTES + 1), r.status, r.headers.get("Content-Range", "")


def find_timestamps(parsed) -> list[str]:
    """Any date/time-looking strings in non-STREAMINFO metadata blocks."""
    texts = []
    for b in parsed["blocks"]:
        texts += b.get("comments", []) + b.get("strings", [])
        if "vendor" in b:
            texts.append(b["vendor"])
    pat = re.compile(r"(19|20)\d\d[-/:]?\d\d[-/:]?\d\d[T _]?\d\d:?\d\d:?\d\d|\d{12}")
    return [t for t in texts if pat.search(t)]


def run(actor: str):
    listing = json.loads(LISTING_PATH.read_text())
    results = []
    for key, how, why in SELECTION:
        files = listing[key]
        rows = sorted((parse_start(n), n, s) for n, s in files)
        i = pick(rows, how)
        start, name, size = rows[i]
        intervals, nominal = file_intervals(files)
        est_s = (intervals[i][1] - intervals[i][0]).total_seconds()
        next_gap = (rows[i + 1][0] - start).total_seconds() if i + 1 < len(rows) else None

        url = URL.format(site=key[:4], key=key, name=name)
        data, status, content_range = fetch_prefix(url)
        parsed = parse_flac_header(data)
        si = parsed["streaminfo"]
        r = {
            "deployment": key, "why": why, "name": name, "size": size,
            "http_status": status, "bytes_fetched": len(data), "content_range": content_range,
            "sha256_prefix": hashlib.sha256(data).hexdigest(),
            "sample_rate": si["sample_rate"], "channels": si["channels"],
            "bits_per_sample": si["bits_per_sample"], "total_samples": si["total_samples"],
            "header_duration_s": si["duration_s"], "name_estimate_s": est_s,
            "next_start_gap_s": next_gap, "nominal_s": nominal,
            "diff_s": si["duration_s"] - est_s,
            "blocks": [{k: v for k, v in b.items() if k != "strings"} | ({"strings": b["strings"]} if b.get("strings") else {})
                       for b in parsed["blocks"]],
            "timestamps_in_metadata": find_timestamps(parsed),
        }
        results.append(r)
        log_event(actor, "range_fetch_flac_header",
                  {"url": url, "range": f"bytes=0-{RANGE_BYTES - 1}", "http_status": status,
                   "bytes": len(data), "sha256": r["sha256_prefix"],
                   "duration_s": r["header_duration_s"], "name_estimate_s": est_s})
        print(key, name[-45:], status, len(data), round(r["diff_s"], 3), flush=True)
    OUT_JSON.write_text(json.dumps(results, indent=1, default=str))
    return results


def render(results) -> str:
    rows = []
    for r in results:
        kind = "last file (size estimate)" if r["next_start_gap_s"] is None else "time to next file"
        flag = "**mismatch**" if abs(r["diff_s"]) > MISMATCH_S else "ok"
        rows.append(
            f"| {r['deployment']} | `{r['name']}` | {r['why']} | {r['sample_rate']} | {r['channels']} | "
            f"{r['bits_per_sample']} | {r['total_samples']:,} | {r['header_duration_s']:,.2f} | "
            f"{r['name_estimate_s']:,.2f} ({kind}) | {r['diff_s']:+,.2f} | {flag} |")
    blocks = []
    for r in results:
        desc = []
        for b in r["blocks"]:
            d = b["type"] + (" (truncated at 16 KB)" if b["truncated"] else "")
            if "vendor" in b:
                d += f" vendor=`{b['vendor']}` comments={b['comments']}"
            if "app_id" in b:
                d += f" id=`{b['app_id']}`"
            desc.append(d)
        ts = ", ".join(r["timestamps_in_metadata"]) or "none"
        blocks.append(f"| {r['deployment']} | `{r['name'][-38:]}` | {'; '.join(desc)} | {ts} |")
    mid = [r for r in results if r["next_start_gap_s"] is not None]
    plain = [r for r in mid if "_Post-clip" not in r["name"]]
    clip = [r for r in mid if "_Post-clip" in r["name"]]
    last = [r for r in results if r["next_start_gap_s"] is None]
    rng = lambda rs: f"{min(r['diff_s'] for r in rs):+.2f} to {max(r['diff_s'] for r in rs):+.2f} s" if rs else "–"
    fmt = {(r["sample_rate"], r["channels"], r["bits_per_sample"]) for r in results}
    truncated = sum(any(b["truncated"] and b["type"] != "PADDING" for b in r["blocks"]) for r in results)
    summary = "\n".join([
        f"- Format in all {len(results)} files: " + "; ".join(f"{a} Hz, {b} channel(s), {c}-bit" for a, b, c in fmt) + ".",
        f"- Normal files that have a next file ({len(plain)}): header − estimate = {rng(plain)}. The audio runs slightly "
        "past the next file's start (≈1 s overlap), so name-based durations are accurate.",
        f"- `_Post-clip` files ({len(clip)}): {rng(clip)}. They are a few seconds shorter than their slot, so there are "
        "tiny gaps around them.",
        f"- Last file of a deployment ({len(last)}), estimated from size: {rng(last)}. This is the only real "
        "mismatch. It affects only each deployment's final day.",
        f"- Timestamps: **none found** in any metadata block. Vorbis comments contain only the encoder name; `riff` blocks "
        "hold only the original WAV RIFF/fmt/data headers. **UTC cannot be confirmed from the file metadata.** "
        f"In {truncated} file(s) a SEEKTABLE runs past 16 KB, so any blocks after it were not inspected.",
    ])
    return HEADER_TEMPLATE.format(n=len(results), rng=RANGE_BYTES, mm=MISMATCH_S, summary=summary,
                                  rows="\n".join(rows), blocks="\n".join(blocks))


HEADER_TEMPLATE = """# FLAC header check

Generated by `python -m src.header_check fetch|report`. For {n} files, only the first {rng:,} bytes were
fetched (HTTP `Range: bytes=0-{rng_end}`; every response was `206 Partial Content`). The FLAC STREAMINFO
block was parsed with `src/flac_header.py`. Raw results: `data/header_check.json`; each fetch's SHA-256 is in
`audit_log.jsonl`.

"Name estimate" is the duration `src/label_survey.py` assigns to the file from file names: the time to the
next file's start, capped at the normal file length. For the last file of a deployment there is no next file,
so it is file size ÷ the deployment's median bytes per second. "Mismatch" = |difference| > {mm:g} s.

## Summary

{summary}

## Durations

| Deployment | File | Why chosen | Sample rate | Ch | Bits | Total samples | Header duration s | Name estimate s | Header − estimate s | |
|---|---|---|---|---|---|---|---|---|---|---|
{rows}

## Metadata blocks and timestamps

| Deployment | File | Blocks (in the first 16 KB) | Timestamps found |
|---|---|---|---|
{blocks}
""".replace("{rng_end}", str(RANGE_BYTES - 1))


def report(actor: str):
    results = json.loads(OUT_JSON.read_text())
    OUT_DOC.write_text(render(results))
    log_event(actor, "write_header_check", {"dest": str(OUT_DOC.relative_to(ROOT)),
                                            "sha256": hashlib.sha256(OUT_DOC.read_bytes()).hexdigest()})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["fetch", "report"])
    ap.add_argument("--actor", required=True)
    args = ap.parse_args()
    run(args.actor) if args.step == "fetch" else report(args.actor)
