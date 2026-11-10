"""Pilot: score the pilot train/val days with Google's multispecies whale model.

    python -m src.pilot --actor <name> [--workers 5] [--limit N] [--skip-existing]

For each day in data/pilot_days.csv (train/val only; test days are refused):
  * every audio file overlapping that UTC day is streamed into memory (never written to disk),
    decoded with soundfile and resampled 48 kHz -> 24 kHz with soxr (VHQ, anti-aliased),
    in a pool of worker processes;
  * each file is split at UTC midnight and cut into non-overlapping 5 s windows (120,000
    samples at 24 kHz) starting at the file's (or midnight's) start; a trailing partial
    window is dropped;
  * the model runs on the GPU in the main process. Per window we keep all 12 class scores
    (`score` signature = sigmoid of logits on the centre 128 of 161 front-end frames);
    per 5-minute block (by window start) we keep the mean 1280-d `features` embedding
    of that same crop, as float16.
Output: data/pilot/<site>_<deployment>_<date>.npz. Labels are never read here.
"""

import argparse
import concurrent.futures as cf
import io
import json
import multiprocessing as mp
import os
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from src.audit import log_event
from src.header_check import URL
from src.label_survey import LISTING_PATH, ROOT, file_intervals, parse_start

MODEL_DIR = ROOT / "data/models/models/google/multispecies-whale/tensorFlow2/default/2"
PILOT_DAYS = ROOT / "data" / "pilot_days.csv"
OUT_DIR = ROOT / "data" / "pilot"
SR_IN, SR = 48000, 24000      # file rate; model rate (model metadata: input_sample_rate)
WIN = 120000                  # model metadata: context_width_samples (5 s at 24 kHz)
WIN_S = WIN / SR
BLOCK_S = 300                 # embedding block length
CROP = (16, 144)              # centre 128 of 161 front-end frames; reproduces `score` exactly
BATCH = 128
CHUNK = 8 * 1024 * 1024
DAY = timedelta(days=1)


def midnight(d):
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def plan_tasks(days: pd.DataFrame, listing: dict):
    """Return one task per audio file overlapping any pilot day: (url, name, start, next_start, days)."""
    tasks = {}
    for (site, dep), grp in days.groupby(["site", "deployment"]):
        key = f"{site}_{dep}"
        files = sorted(listing[key], key=lambda f: parse_start(f[0]))
        intervals, _ = file_intervals(files)
        starts = [parse_start(n) for n, _ in files]
        for d in grp["date"]:
            d0 = midnight(datetime.fromisoformat(d))
            for i, ((name, size), (s, e, _)) in enumerate(zip(files, intervals)):
                if s < d0 + DAY and e > d0:
                    t = tasks.setdefault(name, {
                        "url": URL.format(site=site, key=key, name=name), "name": name,
                        "listed_bytes": size, "start": s.isoformat(),
                        "next_start": starts[i + 1].isoformat() if i + 1 < len(starts) else None,
                        "days": []})
                    t["days"].append(f"{key}_{d}")
    return list(tasks.values())


def fetch(url, tries=3):
    for k in range(tries):
        try:
            buf = io.BytesIO()
            with urllib.request.urlopen(url, timeout=120) as r:
                while chunk := r.read(CHUNK):
                    buf.write(chunk)
            return buf
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))


def decode_task(task):
    """Worker: stream, decode, resample and split one file at UTC midnights. Nothing touches disk."""
    import soundfile as sf
    import soxr

    info = {"name": task["name"], "flags": []}
    t0 = time.perf_counter()
    buf = fetch(task["url"])
    info["download_s"] = time.perf_counter() - t0
    info["bytes"] = buf.tell()
    if info["bytes"] != task["listed_bytes"]:
        info["flags"].append(f"size {info['bytes']} != listed {task['listed_bytes']}")
    buf.seek(0)
    t1 = time.perf_counter()
    # Decode and resample in chunks (bounded memory); ResampleStream keeps the filter state
    # across chunks, so the result equals one-shot resampling of the whole file.
    start = datetime.fromisoformat(task["start"])
    gap = ((datetime.fromisoformat(task["next_start"]) - start).total_seconds()
           if task["next_start"] else None)
    out, n_in, peak, zeros, clips = [], 0, 0, 0, 0
    with sf.SoundFile(buf) as f:
        sr, ch = f.samplerate, f.channels
        info["sr"], info["channels"] = sr, ch
        if sr != SR_IN:
            info["flags"].append(f"sample rate {sr}")
        if ch != 1:
            info["flags"].append(f"{ch} channels; using channel 0")
        info["decoded_s"] = f.frames / sr
        keep = f.frames
        if gap is not None and f.frames / sr > gap + 2:
            info["flags"].append(f"overlaps next file by {f.frames / sr - gap:.1f}s; trimmed")
            keep = int(gap * sr)
        rs = soxr.ResampleStream(sr, SR, 1, dtype="int16", quality="VHQ") if sr != SR else None
        step = 60 * sr
        while n_in < keep:
            a = f.read(min(step, keep - n_in), dtype="int16", always_2d=True)
            if not len(a):
                break
            a = np.ascontiguousarray(a[:, 0])
            n_in += len(a)
            peak = max(peak, int(np.abs(a.astype(np.int32)).max()))
            zeros += int((a == 0).sum())
            clips += int(((a >= 32767) | (a <= -32768)).sum())
            last = n_in >= keep
            out.append(rs.resample_chunk(a, last=last) if rs else a)
        if rs and n_in < keep:
            out.append(rs.resample_chunk(np.zeros(0, np.int16), last=True))
    del buf
    if n_in < keep:
        info["flags"].append(f"decoded {n_in} of {keep} frames")
    y = np.concatenate(out) if out else np.zeros(0, np.int16)
    del out
    info["decode_resample_s"] = time.perf_counter() - t1
    info["peak"] = peak
    info["zero_frac"] = zeros / max(n_in, 1)
    info["clip_frac"] = clips / max(n_in, 1)
    expected = round(n_in * SR / sr)
    if abs(len(y) - expected) > SR // 10:
        info["flags"].append(f"resampled length {len(y)} vs expected {expected}")

    end = start + timedelta(seconds=len(y) / SR)
    segs = []
    for dkey in task["days"]:
        d0 = midnight(datetime.fromisoformat(dkey.split("_")[-1]))
        s, e = max(start, d0), min(end, d0 + DAY)
        if e <= s:
            continue
        i0 = round((s - start).total_seconds() * SR)
        i1 = round((e - start).total_seconds() * SR)
        segs.append((dkey, (s - d0).total_seconds(), y[i0:i1].copy()))
    return info, segs


class DayAccumulator:
    def __init__(self):
        self.t, self.scores, self.files = [], [], []
        self.emb_sum = defaultdict(lambda: np.zeros(1280, np.float64))
        self.emb_n = defaultdict(int)

    def add(self, t, scores, emb):
        self.t.append(t)
        self.scores.append(scores)
        for b, v in zip((t // BLOCK_S).astype(int), emb):
            self.emb_sum[b] += v
            self.emb_n[b] += 1


def main(actor, workers, limit, skip_existing=False):
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    import tensorflow as tf

    gpus = tf.config.list_physical_devices("GPU")
    for g in gpus:
        tf.config.experimental.set_memory_growth(g, True)
    model = tf.saved_model.load(str(MODEL_DIR))
    meta = model.metadata()
    classes = [c.decode() for c in meta["class_names"].numpy()]
    assert int(meta["input_sample_rate"]) == SR and int(meta["context_width_samples"]) == WIN

    @tf.function
    def run(w):
        sp = model.front_end(w)[:, CROP[0]:CROP[1]]
        return tf.sigmoid(model.logits(sp)), model.features(sp)

    days = pd.read_csv(PILOT_DAYS, dtype={"deployment": str})[["split", "site", "deployment", "date"]]
    if set(days["split"]) != {"trainval"}:
        raise SystemExit("pilot list contains non-train/val days; refusing")
    if limit:
        days = days.head(limit)
    resumed = []
    if skip_existing:
        prior = completed_days()
        keys = days["site"] + "_" + days["deployment"] + "_" + days["date"]
        resumed = [prior[k] for k in keys if k in prior]
        days = days[~keys.isin(prior)]
    listing = json.loads(LISTING_PATH.read_text())
    tasks = plan_tasks(days, listing)
    remaining = defaultdict(int)
    for t in tasks:
        for d in t["days"]:
            remaining[d] += 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log_event(actor, "pilot_start", {
        "days": len(days), "files": len(tasks), "workers": workers, "gpu": [g.name for g in gpus],
        "model_dir": str(MODEL_DIR.relative_to(ROOT)), "resampler": "soxr VHQ 48000->24000",
        "window_samples": WIN, "block_s": BLOCK_S, "audio_saved_to_disk": False,
        "skipped_existing": len(resumed)})

    acc = defaultdict(DayAccumulator)
    gpu_s, n_windows, day_reports = 0.0, 0, []
    day_t0 = {}
    T0 = time.perf_counter()
    ctx = mp.get_context("spawn")
    with cf.ProcessPoolExecutor(workers, mp_context=ctx) as pool:
        pending, it = {}, iter(tasks)
        def refill():
            while len(pending) < workers + 1:
                t = next(it, None)
                if t is None:
                    return
                for d in t["days"]:
                    day_t0.setdefault(d, time.perf_counter())
                pending[pool.submit(decode_task, t)] = t
        refill()
        while pending:
            done, _ = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
            for fut in done:
                task = pending.pop(fut)
                info, segs = fut.result()
                for dkey, off, y in segs:
                    n = len(y) // WIN
                    w = y[: n * WIN].reshape(n, WIN)
                    tstart = off + WIN_S * np.arange(n)
                    sc, em = [], []
                    g0 = time.perf_counter()
                    for i in range(0, n, BATCH):
                        xb = (w[i:i + BATCH].astype(np.float32) / 32768.0)[..., None]
                        s, e = run(tf.constant(xb))
                        sc.append(s.numpy())
                        em.append(e.numpy())
                    gpu_s += time.perf_counter() - g0
                    n_windows += n
                    a = acc[dkey]
                    if n:
                        a.add(tstart, np.concatenate(sc), np.concatenate(em))
                    a.files.append({**{k: v for k, v in info.items()}, "seg_offset_s": off,
                                    "seg_windows": n})
                for dkey in task["days"]:
                    remaining[dkey] -= 1
                    if remaining[dkey] == 0:
                        day_reports.append(save_day(dkey, acc.pop(dkey, DayAccumulator()), classes,
                                                    time.perf_counter() - day_t0[dkey], actor))
            refill()
    total = time.perf_counter() - T0
    summary = {"days": len(day_reports), "windows": n_windows, "total_s": round(total, 1),
               "gpu_s": round(gpu_s, 1), "gpu_windows_per_s": round(n_windows / gpu_s, 1) if gpu_s else None,
               "end_to_end_windows_per_s": round(n_windows / total, 1),
               "mean_s_per_day": round(total / max(len(day_reports), 1), 1),
               "projection_700_days_h": round(700 * total / max(len(day_reports), 1) / 3600, 2),
               "flagged_days": [r["day"] for r in resumed + day_reports if r["flags"]]}
    if resumed:
        # Timing fields above cover this run only; resumed days come from their audit-log entries.
        summary["resumed_days"] = len(resumed)
        summary["total_days"] = len(resumed) + len(day_reports)
    (OUT_DIR / "pilot_report.json").write_text(
        json.dumps({"summary": summary, "days": resumed + day_reports}, indent=1))
    log_event(actor, "pilot_end", summary)
    print(json.dumps(summary, indent=1))


def completed_days(log_path=None):
    """Days whose .npz exists and matches the sha256 in that day's latest pilot_day log entry.

    Returns {day: report}. A day whose file is missing or whose hash differs is not complete.
    """
    import hashlib

    from src.audit import DEFAULT_LOG

    latest = {}
    for line in open(log_path or DEFAULT_LOG, encoding="utf-8"):
        e = json.loads(line)
        if e["action"] == "pilot_day":
            latest[e["details"]["day"]] = e["details"]
    done = {}
    for day, rep in latest.items():
        path = ROOT / rep["npz"]
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == rep["sha256"]:
            done[day] = rep
    return done


def save_day(dkey, a: DayAccumulator, classes, wall_s, actor):
    import hashlib

    if a.t:
        t = np.concatenate(a.t)
        sc = np.concatenate(a.scores).astype(np.float32)
        order = np.argsort(t, kind="stable")
        t, sc = t[order], sc[order]
    else:
        t, sc = np.zeros(0), np.zeros((0, len(classes)), np.float32)
    blocks = np.array(sorted(a.emb_sum), dtype=np.int32)
    emb = np.stack([a.emb_sum[b] / a.emb_n[b] for b in blocks]).astype(np.float16) if len(blocks) \
        else np.zeros((0, 1280), np.float16)
    bn = np.array([a.emb_n[b] for b in blocks], dtype=np.int32)
    hb = sc[:, classes.index("Mn")] if len(sc) else np.zeros(0, np.float32)

    flags = sorted({f for fi in a.files for f in fi["flags"]})
    hours = len(t) * WIN_S / 3600
    if hours < 20:
        flags.append(f"only {hours:.2f} h of windows")
    if len(t) and (np.diff(t) < WIN_S - 1e-6).any():
        flags.append("overlapping windows")
    if not np.isfinite(sc).all():
        flags.append("non-finite scores")
    if any(fi["peak"] == 0 for fi in a.files):
        flags.append("a file is all zeros")
    if any(fi["zero_frac"] > 0.01 for fi in a.files):
        flags.append("a file has >1% exact-zero samples")
    if any(fi["clip_frac"] > 0.001 for fi in a.files):
        flags.append("a file has >0.1% clipped samples")
    gaps = np.diff(t)
    big_gaps = int((gaps > WIN_S + 60).sum()) if len(t) else 0
    if big_gaps:
        flags.append(f"{big_gaps} gap(s) >1 min between windows")

    path = OUT_DIR / f"{dkey}.npz"
    np.savez_compressed(path, window_start_s=t, scores=sc, class_names=np.array(classes),
                        humpback=hb, block_start_s=blocks * BLOCK_S, block_emb=emb, block_n_windows=bn,
                        files=np.array(json.dumps(a.files)))
    rep = {"day": dkey, "windows": int(len(t)), "hours": round(hours, 3), "files": len(a.files),
           "wall_s": round(wall_s, 1), "blocks": int(len(blocks)),
           "humpback_median": float(np.median(hb)) if len(hb) else None,
           "humpback_max": float(hb.max()) if len(hb) else None,
           "max_other_class_median": float(np.median(np.delete(sc, classes.index("Mn"), 1).max(1))) if len(sc) else None,
           "min_peak": min(fi["peak"] for fi in a.files) if a.files else None,
           "flags": flags, "npz": str(path.relative_to(ROOT)),
           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    log_event(actor, "pilot_day", rep)
    print(dkey, rep["windows"], rep["hours"], rep["wall_s"], flags, flush=True)
    return rep


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--actor", required=True)
    p.add_argument("--workers", type=int, default=5)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--skip-existing", action="store_true",
                   help="resume: skip days whose .npz matches their logged sha256")
    a = p.parse_args()
    main(a.actor, a.workers, a.limit, a.skip_existing)
