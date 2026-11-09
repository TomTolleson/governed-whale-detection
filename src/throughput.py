"""Measure streaming throughput for one full audio file, without saving it to disk.

    python -m src.throughput --actor <name>

Picks the non-edge file closest to 400 MB (300-500 MB allowed) from the eligible
deployments, downloads it anonymously into memory, decodes it with soundfile,
then discards it. Logs the file name, SHA-256, MB/s and decode time, and
estimates hours to stream 100/300/600 eligible days at that rate.
"""

import argparse
import hashlib
import io
import json
import statistics
import time
import urllib.request

import pandas as pd
import soundfile as sf

from src.audit import log_event
from src.header_check import URL
from src.label_survey import LISTING_PATH, ROOT, parse_start

TARGET = 400e6
LO, HI = 300e6, 500e6
CHUNK = 8 * 1024 * 1024
DAYS = (100, 300, 600)
MB = 1e6  # MB = 10^6 bytes throughout


def pick_file(listing, eligible_deps):
    best = None
    for key in sorted(eligible_deps):
        files = sorted(listing[key], key=lambda f: parse_start(f[0]))
        for name, size in files[1:-1]:  # skip first/last (partial, odd suffixes)
            if LO <= size <= HI and (best is None or abs(size - TARGET) < abs(best[2] - TARGET)):
                best = (key, name, size)
    return best


def bytes_per_second(files):
    """Median bytes per audio second over full-length files (as in label_survey)."""
    rows = sorted((parse_start(n), s) for n, s in files)
    gaps = [(b[0] - a[0]).total_seconds() for a, b in zip(rows, rows[1:])]
    nominal = statistics.median(gaps)
    return statistics.median(s / g for (_, s), g in zip(rows, gaps) if g > 0.9 * nominal)


def run(actor):
    listing = json.loads(LISTING_PATH.read_text())
    days = pd.read_csv(ROOT / "data" / "day_table.csv", dtype={"deployment": str})
    elig = days[days.eligible]
    elig_keys = {f"{s}_{d}" for s, d in zip(elig.site, elig.deployment)}

    key, name, size = pick_file(listing, elig_keys)
    site = key.split("_")[0]
    url = URL.format(site=site, key=key, name=name)
    log_event(actor, "throughput_start", {"deployment": key, "file": name,
                                          "listed_bytes": size, "url": url, "saved_to_disk": False})

    buf = io.BytesIO()
    h = hashlib.sha256()
    t0 = time.perf_counter()
    with urllib.request.urlopen(urllib.request.Request(url), timeout=120) as r:
        status = r.status
        while chunk := r.read(CHUNK):
            buf.write(chunk)
            h.update(chunk)
    dl_s = time.perf_counter() - t0
    n = buf.tell()

    buf.seek(0)
    t1 = time.perf_counter()
    audio, sr = sf.read(buf, dtype="int16")
    dec_s = time.perf_counter() - t1
    audio_s = len(audio) / sr
    channels = 1 if audio.ndim == 1 else audio.shape[1]
    del audio, buf  # discard

    mbps = n / MB / dl_s

    # Bytes per eligible day: each deployment's bytes/s x that day's audio hours.
    rate = {k: bytes_per_second(listing[k]) for k in elig_keys}
    day_bytes = [rate[f"{s}_{d}"] * h_ * 3600
                 for s, d, h_ in zip(elig.site, elig.deployment, elig.audio_hours)]
    mean_day = statistics.mean(day_bytes)
    mean_hours = elig.audio_hours.mean()
    dec_per_audio_s = dec_s / audio_s
    est = {}
    for d in DAYS:
        stream_h = d * mean_day / MB / mbps / 3600
        decode_h = d * mean_hours * 3600 * dec_per_audio_s / 3600
        est[d] = {"stream_h": round(stream_h, 2), "decode_h_single_core": round(decode_h, 2),
                  "data_GB": round(d * mean_day / 1e9, 1)}

    result = {
        "deployment": key, "file": name, "http_status": status, "bytes": n,
        "listed_bytes": size, "sha256": h.hexdigest(), "download_s": round(dl_s, 2),
        "MB_per_s": round(mbps, 1), "decode_s": round(dec_s, 2), "sample_rate": sr,
        "channels": channels, "audio_s": round(audio_s, 2),
        "decode_x_realtime": round(audio_s / dec_s, 1),
        "mean_bytes_per_eligible_day": round(mean_day), "mean_audio_hours_per_eligible_day": round(mean_hours, 2),
        "eligible_days_available": int(len(elig)), "estimates": est,
        "saved_to_disk": False, "note": "single measurement, one file, one connection; MB = 10^6 bytes",
    }
    log_event(actor, "throughput_result", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--actor", required=True)
    run(ap.parse_args().actor)
