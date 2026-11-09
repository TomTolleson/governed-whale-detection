"""Survey humpback day-level labels against the audio that exists for each day.

    python -m src.label_survey fetch    # download 36 label CSVs + audio listings (no audio)
    python -m src.label_survey report   # write docs/label_survey.md from data/

Audio hours are ESTIMATED from file names and sizes only (no audio is read):
each file is assumed to last until the next file starts, capped at the
deployment's normal file length. The last file's length is estimated from
its size. See docs/label_survey.md for the reasoning and its limits.
"""

import argparse
import hashlib
import json
import re
import statistics
import warnings
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.audit import log_event

warnings.filterwarnings("ignore", category=FutureWarning)

BUCKET = "noaa-passive-bioacoustic/sanctsound"
SITES = ["sb01", "sb02", "sb03"]
DEPLOYMENTS = [f"{n:02d}" for n in range(1, 13)]
ROOT = Path(__file__).resolve().parent.parent
LABEL_DIR = ROOT / "data" / "labels"
LISTING_PATH = ROOT / "data" / "audio_listing.json"
DOC_PATH = ROOT / "docs" / "label_survey.md"

LOW_PRESENCE = 0.80   # deployments below this presence rate are listed
MIN_HOURS = 20.0      # labelled days with less audio than this are reported

# Deployments 01-03: ..._20181112T180000Z.flac, optionally followed by
# _Post-Deployment, _Pre-Retrieval, _Post-clip or _Pre-Retrieval_Post-clip.
ISO_NAME = re.compile(r"_(\d{8}T\d{6})Z(?:_[A-Za-z-]+)*\.flac$")
# Deployments 04+: ..._190601180000.flac  (YYMMDDHHMMSS, assumed UTC)
SHORT_NAME = re.compile(r"_(\d{12})\.flac$")


def parse_start(name: str) -> datetime:
    """Return the UTC start time encoded in a SanctSound audio file name."""
    m = ISO_NAME.search(name)
    if m:
        dt = datetime.strptime(m.group(1), "%Y%m%dT%H%M%S")
    else:
        m = SHORT_NAME.search(name)
        if not m:
            raise ValueError(f"unrecognised audio file name: {name}")
        dt = datetime.strptime(m.group(1), "%y%m%d%H%M%S")
    return dt.replace(tzinfo=timezone.utc)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- fetch (network)

def fetch(actor: str) -> None:
    import gcsfs

    fs = gcsfs.GCSFileSystem(token="anon")
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    listing = {}
    for site in SITES:
        for dep in DEPLOYMENTS:
            key = f"{site}_{dep}"
            src = (f"{BUCKET}/products/detections/{site}/sanctsound_{key}_humpbackwhale_1d/"
                   f"data/SanctSound_{key.upper()}_humpbackwhale_1d.csv")
            dest = LABEL_DIR / f"{key}.csv"
            dest.write_bytes(fs.cat(src))
            log_event(actor, "download_label_csv",
                      {"src": f"gs://{src}", "dest": str(dest.relative_to(ROOT)),
                       "bytes": dest.stat().st_size, "sha256": sha256_file(dest)})

            audio_dir = f"{BUCKET}/audio/{site}/sanctsound_{key}/audio"
            listing[key] = [[e["name"].rsplit("/", 1)[-1], int(e["size"])]
                            for e in fs.ls(audio_dir, detail=True) if e["type"] == "file"]
            print(key, len(listing[key]), "audio files listed", flush=True)
    LISTING_PATH.write_text(json.dumps(listing, indent=0))
    log_event(actor, "save_audio_listing",
              {"dest": str(LISTING_PATH.relative_to(ROOT)), "deployments": len(listing),
               "files": sum(len(v) for v in listing.values()),
               "sha256": sha256_file(LISTING_PATH), "audio_downloaded": False})


# ---------------------------------------------------------------- analysis (offline)

def file_intervals(files):
    """Estimate (start, end, possible_gap) for each audio file of one deployment.

    files: list of (name, size_bytes). Duration = time to the next file's start,
    capped at the deployment's normal file length (median start-to-start interval).
    The last file's duration comes from its size and the deployment's median
    bytes-per-second. possible_gap is True when the next file started more than
    2 minutes later than the normal schedule (recorder may have stopped).
    """
    rows = sorted((parse_start(n), n, s) for n, s in files)
    starts = [r[0] for r in rows]
    gaps = [(b - a).total_seconds() for a, b in zip(starts, starts[1:])]
    nominal = statistics.median(gaps)
    full = [(s, g) for (_, _, s), g in zip(rows, gaps) if g > 0.9 * nominal]
    rate = statistics.median(s / g for s, g in full)  # bytes per second of audio

    out = []
    for i, (start, _, size) in enumerate(rows):
        by_size = size / rate
        if i < len(gaps):
            dur = min(gaps[i], nominal)
            possible_gap = gaps[i] > nominal + 120
        else:
            dur = min(by_size, nominal)
            possible_gap = False
        out.append((start, start + timedelta(seconds=dur), possible_gap))
    return out, nominal


def hours_per_day(intervals):
    """Split [start, end) intervals across UTC midnights; return {date: hours}."""
    hours = defaultdict(float)
    for start, end, _ in intervals:
        t = start
        while t < end:
            next_midnight = datetime.combine(t.date() + timedelta(days=1),
                                             datetime.min.time(), tzinfo=timezone.utc)
            seg_end = min(end, next_midnight)
            hours[t.date()] += (seg_end - t).total_seconds() / 3600
            t = seg_end
    return dict(hours)


def survey_deployment(key, labels: pd.DataFrame, files):
    days = pd.to_datetime(labels["ISOStartTime"]).dt.date
    intervals, nominal = file_intervals(files)
    hpd = hours_per_day(intervals)
    label_days = set(days)
    presence = dict(zip(days, labels["Presence"]))
    return {
        "key": key,
        "start": min(days), "end": max(days), "n_days": len(days),
        "n_present": int(labels["Presence"].sum()),
        "rate": float(labels["Presence"].mean()),
        "months": sorted({d.strftime("%Y-%m") for d in days}),
        "n_files": len(files),
        "nominal_h": nominal / 3600,
        "audio_hours": sum(hpd.values()),
        "possible_gaps": sum(g for _, _, g in intervals),
        "short_days": sorted((d, hpd.get(d, 0.0)) for d in label_days if hpd.get(d, 0.0) < MIN_HOURS),
        "unlabelled_days": sorted((d, h) for d, h in hpd.items() if d not in label_days),
        "zero_audio_days": sorted((d, int(presence[d])) for d in label_days if hpd.get(d, 0.0) == 0),
        "dup_label_days": len(days) - len(label_days),
        "values": sorted(labels["Presence"].unique().tolist()),
    }


def boundary_days(label_dir=None):
    """Site-days labelled by two deployments (changeover days); return (site, day, {dep: presence})."""
    label_dir = label_dir or LABEL_DIR
    seen = defaultdict(dict)
    for site in SITES:
        for dep in DEPLOYMENTS:
            df = pd.read_csv(label_dir / f"{site}_{dep}.csv")
            for day, p in zip(df["ISOStartTime"], df["Presence"]):
                seen[(site, day)][dep] = int(p)
    return sorted((site, day, deps) for (site, day), deps in seen.items() if len(deps) > 1)


def run_survey():
    listing = json.loads(LISTING_PATH.read_text())
    results = []
    for site in SITES:
        for dep in DEPLOYMENTS:
            key = f"{site}_{dep}"
            labels = pd.read_csv(LABEL_DIR / f"{key}.csv")
            results.append(survey_deployment(key, labels, listing[key]))
    return results


# ---------------------------------------------------------------- report

def _summary_row(name, rs):
    n = sum(r["n_days"] for r in rs)
    p = sum(r["n_present"] for r in rs)
    return (f"| **{name}** | {min(r['start'] for r in rs)} | {max(r['end'] for r in rs)} | "
            f"**{n}** | **{p}** | **{p / n:.1%}** | {len(rs)} deployments | "
            f"{sum(r['audio_hours'] for r in rs):,.0f} | {sum(len(r['short_days']) for r in rs)} | "
            f"{sum(len(r['unlabelled_days']) for r in rs)} |")


def render(results) -> str:
    lines = [
        "| Deployment | Start | End | Days | Present | Rate | Months covered | Audio h (est.) "
        f"| Labelled days < {MIN_HOURS:.0f} h | Audio days w/o label |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for site in SITES:
        rs = [r for r in results if r["key"].startswith(site)]
        for r in rs:
            lines.append(
                f"| {r['key']} | {r['start']} | {r['end']} | {r['n_days']} | {r['n_present']} | "
                f"{r['rate']:.1%} | {', '.join(r['months'])} | {r['audio_hours']:,.0f} | "
                f"{len(r['short_days'])} | {len(r['unlabelled_days'])} |")
        lines.append(_summary_row(site, rs))
    lines.append(_summary_row("ALL", results))
    table = "\n".join(lines)

    low = [r for r in results if r["rate"] < LOW_PRESENCE]
    low_txt = "\n".join(
        f"- **{r['key']}**: {r['rate']:.1%} ({r['n_present']}/{r['n_days']} days), "
        f"{r['start']} → {r['end']}" for r in low) or "- none"

    def fmt(ds):
        return ", ".join(f"{d} ({h:.1f} h)" for d, h in ds) or "–"

    detail = "\n".join(
        f"| {r['key']} | {r['nominal_h']:.1f} | {r['possible_gaps']} | {fmt(r['short_days'])} | "
        f"{fmt(r['unlabelled_days'])} |" for r in results)

    zero = "\n".join(
        f"| {r['key']} | {len(r['zero_audio_days'])} | {sum(p for _, p in r['zero_audio_days'])} | "
        f"{r['zero_audio_days'][0][0]} → {r['zero_audio_days'][-1][0]} |"
        for r in results if r["zero_audio_days"]) or "| none | | | |"

    bd = boundary_days()
    conflicts = [b for b in bd if len(set(b[2].values())) > 1]
    bd_txt = (f"{len(bd)} site-days are labelled by both the outgoing and the incoming deployment "
              f"(the changeover day). **{len(conflicts)} of them disagree:**\n\n"
              "| Site | Day | Labels (deployment: presence) |\n|---|---|---|\n" +
              "\n".join(f"| {s} | {d} | {', '.join(f'{k}: {v}' for k, v in deps.items())} |"
                         for s, d, deps in conflicts))
    unique_days = sum(r["n_days"] for r in results) - len(bd)

    return TEMPLATE.format(table=table, low=low_txt, detail=detail, zero=zero, boundary=bd_txt,
                           unique_days=unique_days,
                           low_pct=f"{LOW_PRESENCE:.0%}", min_h=f"{MIN_HOURS:.0f}")


TEMPLATE = """# Humpback label survey: Stellwagen Bank, deployments 01–12

Generated by `python -m src.label_survey report` from `data/labels/*.csv` (36 humpbackwhale_1d CSVs,
SHA-256 of each recorded in `audit_log.jsonl`) and `data/audio_listing.json` (names and sizes of
every audio object; **no audio was downloaded**).

Labels: one row per UTC day, `ISOStartTime` (date) and `Presence` (0/1), analyst-screened LFDCS
detections (NOAA ONMS / U.S. Navy SanctSound, https://doi.org/10.25921/saca-sp25).

## Per deployment

{table}

Note: "Days" counts label rows. Changeover days are labelled by two deployments (see below), so the
number of distinct site-days is **{unique_days}**, not the ALL total.

## Labelled days with NO audio in the bucket

These days have a label row but no audio file covers any part of them. They cannot be used for
training or evaluation, and the "0" labels are probably "no data" rather than true absence.

| Deployment | Labelled days with 0 h audio | Of which Presence = 1 | Range |
|---|---|---|---|
{zero}

## Changeover days labelled twice

{boundary}

## Deployments with presence rate below {low_pct}

{low}

## How audio hours were estimated (no audio read)

- Start time comes from the file name. Deployments 01–03 use `..._YYYYMMDDTHHMMSSZ[_suffix].flac`, where
  the suffix is `_Post-Deployment` (first file), `_Pre-Retrieval` (last file), `_Post-clip` or
  `_Pre-Retrieval_Post-clip`. Deployments 04+ use `..._YYMMDDHHMMSS.flac`, **assumed to be UTC**
  (the name has no zone marker).
- Each file is assumed to run until the next file starts, capped at the deployment's normal file length
  (median start-to-start interval: 6 h for deployments 01–02, 4 h from 03 onward). The one file whose real length was
  read earlier (sb02_01 first file, 18,429 s) ends exactly when the next file starts, which supports this.
- The last file of each deployment has no successor, so its length is estimated from its size divided by the
  deployment's median bytes per second, capped at the normal length. FLAC compression varies, so this is
  rough (±~20 %); it only affects the final day.
- **Possible gaps:** an interval is flagged when the next file starts more than 2 minutes later than the normal
  schedule. **No interval in deployments 01–12 is flagged.** Files always start on schedule or early (short
  `_Post-clip` files), so the listing shows no recorder downtime between labelled start and end dates.
  A gap *inside* a file (the file is shorter than its slot) cannot be seen without reading the file header.
  An earlier size-based check flagged 555 intervals, but 551 of them were exactly on schedule. FLAC size
  depends on how noisy the sea is, so size is not a reliable stand-in for duration, and that check was dropped.
- Hours are split across UTC midnights.

## Detail: short labelled days and unlabelled audio days

Normal file length in hours; possible-gap intervals; labelled days with < {min_h} h of estimated audio
(hours in brackets); days with audio but no label row.

| Deployment | File length h | Possible gaps | Labelled days < {min_h} h | Audio days without label |
|---|---|---|---|---|
{detail}
"""


def report(actor: str) -> None:
    results = run_survey()
    DOC_PATH.write_text(render(results))
    log_event(actor, "write_label_survey",
              {"dest": str(DOC_PATH.relative_to(ROOT)), "deployments": len(results),
               "sha256": sha256_file(DOC_PATH)})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["fetch", "report"])
    ap.add_argument("--actor", required=True, help="who is running this, for the audit log")
    args = ap.parse_args()
    fetch(args.actor) if args.step == "fetch" else report(args.actor)
