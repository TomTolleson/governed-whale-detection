"""Score train/val days with Google's multispecies whale model (pipeline v2).

    python -m src.pilot --actor <name> [--days data/sample_days.csv] [--out data/scores/v2]
                        [--workers 5] [--limit N] [--skip-existing] [--allow-dirty]

Only rows with split == "trainval" are read from the day list. Test days are never processed,
and the script has no option to process them.

For each selected UTC day:
  * every audio file overlapping that day is streamed into memory (never written to disk), decoded
    with soundfile and resampled 48 kHz -> 24 kHz with soxr (VHQ, anti-aliased), in worker processes;
  * **any overlap with the next file is trimmed**: a file is cut at the next file's start time. Files
    that then run exactly up to the next file's start are **stitched**, so the 5 s window grid continues
    across the boundary. A file that ends before the next one starts leaves a **real gap**, which is
    not bridged: the leftover partial window is dropped and the grid restarts at the next file. UTC
    midnight always restarts the grid. So windows only cover continuous audio within one day;
  * non-overlapping 5 s windows (120,000 samples at 24 kHz) are scored on the GPU. Per window we keep
    all 12 class scores (`score` = sigmoid of logits on the centre 128 of 161 front-end frames);
  * per 5-minute block (by window start) we keep the mean 1280-d `features` embedding (float16) and the
    mean power in each band of BAND_EDGES_HZ, as dB re full scale (relative levels, not calibrated);
  * per day we record the fraction of exact-zero input samples (48 kHz, before resampling).
Output: <out>/<site>_<deployment>_<date>.npz, stamped with PIPELINE_VERSION and the git commit.
Labels are never read here.
"""

import argparse
import concurrent.futures as cf
import hashlib
import io
import json
import multiprocessing as mp
import os
import subprocess
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from src.audit import DEFAULT_LOG, log_event
from src.header_check import URL
from src.label_survey import LISTING_PATH, ROOT, parse_start

PIPELINE_VERSION = "2"
MODEL_DIR = ROOT / "data/models/models/google/multispecies-whale/tensorFlow2/default/2"
DAYS_CSV = ROOT / "data" / "sample_days.csv"
OUT_DIR = ROOT / "data" / "scores" / "v2"
SR_IN, SR = 48000, 24000      # file rate; model rate (model metadata: input_sample_rate)
WIN = 120000                  # model metadata: context_width_samples (5 s at 24 kHz)
WIN_S = WIN / SR
BLOCK_S = 300                 # block length for embeddings and band levels
CROP = (16, 144)              # centre 128 of 161 front-end frames; reproduces `score` exactly
BATCH = 128
CHUNK = 8 * 1024 * 1024
DAY = timedelta(days=1)
ZERO_FLAG = 0.01              # flag days with more than 1% exact-zero input samples

# Band edges in Hz, fixed before the v2 run (owner decision a, 2026-11-10; eval plan section 5).
# Each band is [lo, hi), using rfft bins of one 5 s window (0.2 Hz spacing). The top octave stops at
# the 12 kHz Nyquist limit of the 24 kHz stream and includes the Nyquist bin.
BANDS = [("50-100", 50, 100), ("100-200", 100, 200), ("200-400", 200, 400), ("400-800", 400, 800),
         ("800-1600", 800, 1600), ("1600-3200", 1600, 3200), ("3200-6400", 3200, 6400),
         ("6400-12000", 6400, 12000), ("50-500", 50, 500)]


def midnight(d):
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


# ---------------------------------------------------------------- band levels

def band_weights(n=WIN, sr=SR):
    """[n//2+1, n_bands] weights so that (|rfft(w*x)|^2 @ W) is the mean-square power of x in each band.

    Hann window w; one-sided spectrum (x2 except DC and Nyquist); divided by n^2 * mean(w^2).
    """
    w = np.hanning(n + 1)[:n]  # periodic Hann
    f = np.arange(n // 2 + 1) * sr / n
    one_sided = np.full(len(f), 2.0)
    one_sided[0] = 1.0
    if n % 2 == 0:
        one_sided[-1] = 1.0
    W = np.zeros((len(f), len(BANDS)))
    for j, (_, lo, hi) in enumerate(BANDS):
        sel = (f >= lo) & ((f < hi) | ((hi == sr / 2) & (f <= hi)))
        W[sel, j] = one_sided[sel]
    return w.astype(np.float32), (W / (n * n * np.mean(w ** 2))).astype(np.float32)


def band_power_np(x):
    """Reference (numpy) band power for windows x [b, WIN] float, in linear mean-square units."""
    w, W = band_weights(x.shape[-1])
    return (np.abs(np.fft.rfft(x * w, axis=-1)) ** 2) @ W


# ---------------------------------------------------------------- planning and stitching

def select_days(days_csv=DAYS_CSV):
    days = pd.read_csv(days_csv, dtype={"deployment": str})
    days = days[days["split"] == "trainval"][["split", "site", "deployment", "date"]]
    if set(days["split"]) != {"trainval"}:
        raise SystemExit("no train/val days selected; refusing")
    return days.reset_index(drop=True)


def plan_tasks(days: pd.DataFrame, listing: dict):
    """One task per audio file overlapping any selected day, in time order within each deployment.

    A file is assumed to end no later than the next file's start (it is trimmed there). The last file of a
    deployment is included if it starts before the day ends.
    """
    tasks = []
    for (site, dep), grp in days.groupby(["site", "deployment"], sort=True):
        key = f"{site}_{dep}"
        files = sorted(listing[key], key=lambda f: parse_start(f[0]))
        starts = [parse_start(n) for n, _ in files]
        wanted = [midnight(datetime.fromisoformat(d)) for d in grp["date"]]
        for i, (name, size) in enumerate(files):
            s = starts[i]
            e = starts[i + 1] if i + 1 < len(files) else s + 2 * DAY
            ds = [d0 for d0 in wanted if s < d0 + DAY and e > d0]
            if ds:
                tasks.append({
                    "key": key, "url": URL.format(site=site, key=key, name=name), "name": name,
                    "listed_bytes": size, "start": s.isoformat(),
                    "prev_name": files[i - 1][0] if i else None,
                    "next_start": starts[i + 1].isoformat() if i + 1 < len(files) else None,
                    "days": [f"{key}_{d0.date().isoformat()}" for d0 in ds]})
    return tasks


def trim_target(n_out, gap_s, sr=SR):
    """Return (keep, contiguous): output samples to keep and whether the file reaches the next file's start.

    n_out: resampled length. gap_s: seconds from this file's start to the next file's start (None if last).
    """
    if gap_s is None:
        return n_out, False
    target = round(gap_s * sr)
    if n_out >= target:
        return target, True
    return n_out, False


def day_pieces(t0: datetime, n: int, sr=SR):
    """Split n samples starting at t0 at UTC midnights. Yields (date_iso, offset_in_day_s, i0, i1)."""
    end = t0 + timedelta(seconds=n / sr)
    a = t0
    while a < end:
        d0 = midnight(a)
        b = min(end, d0 + DAY)
        i0 = round((a - t0).total_seconds() * sr)
        i1 = n if b == end else round((b - t0).total_seconds() * sr)
        yield d0.date().isoformat(), (a - d0).total_seconds(), i0, i1
        a = b


def zeros_by_day(start: datetime, zeros_per_s, samples_per_s):
    """Sum per-second zero and sample counts by UTC date. Second i covers [start+i, start+i+1)."""
    out = defaultdict(lambda: [0, 0])
    if not len(zeros_per_s):
        return out
    secs = np.arange(len(zeros_per_s))
    d0 = midnight(start)
    day_idx = np.floor(((start - d0).total_seconds() + secs) / 86400).astype(int)
    for k in np.unique(day_idx):
        m = day_idx == k
        date = (d0 + timedelta(days=int(k))).date().isoformat()
        out[date][0] += int(zeros_per_s[m].sum())
        out[date][1] += int(samples_per_s[m].sum())
    return out


# ---------------------------------------------------------------- worker

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
    """Worker: stream, decode, resample and trim one file at the next file's start. Nothing touches disk."""
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
    start = datetime.fromisoformat(task["start"])
    gap = ((datetime.fromisoformat(task["next_start"]) - start).total_seconds()
           if task["next_start"] else None)
    out, n_in, peak, clips = [], 0, 0, 0
    zps, sps = [], []
    with sf.SoundFile(buf) as f:
        sr, ch = f.samplerate, f.channels
        info["sr"], info["channels"] = sr, ch
        if sr != SR_IN:
            info["flags"].append(f"sample rate {sr}")
        if ch != 1:
            info["flags"].append(f"{ch} channels; using channel 0")
        info["decoded_s"] = f.frames / sr
        # Decode 0.1 s past the next file's start so the resampler's tail is complete; cut exactly at 24 kHz.
        count_limit = f.frames if gap is None else min(f.frames, round(gap * sr))
        keep_in = f.frames if gap is None else min(f.frames, round(gap * sr) + sr // 10)
        info["overlap_s"] = round(max(0.0, f.frames / sr - gap), 4) if gap is not None else 0.0
        if info["overlap_s"] > 2:
            info["flags"].append(f"overlaps next file by {info['overlap_s']:.1f}s; trimmed")
        rs = soxr.ResampleStream(sr, SR, 1, dtype="int16", quality="VHQ") if sr != SR else None
        step = 60 * sr
        while n_in < keep_in:
            a = f.read(min(step, keep_in - n_in), dtype="int16", always_2d=True)
            if not len(a):
                break
            a = np.ascontiguousarray(a[:, 0])
            c = a[: max(0, count_limit - n_in)]  # stats cover only audio that is kept
            if len(c):
                peak = max(peak, int(np.abs(c.astype(np.int32)).max()))
                clips += int(((c >= 32767) | (c <= -32768)).sum())
                idx = np.arange(0, len(c), sr)  # n_in is a multiple of sr, so seconds align with the file
                zps.append(np.add.reduceat((c == 0).astype(np.int32), idx))
                sps.append(np.diff(np.append(idx, len(c))).astype(np.int32))
            n_in += len(a)
            out.append(rs.resample_chunk(a, last=n_in >= keep_in) if rs else a)
        if rs and n_in < keep_in:
            out.append(rs.resample_chunk(np.zeros(0, np.int16), last=True))
    del buf
    if n_in < keep_in:
        info["flags"].append(f"decoded {n_in} of {keep_in} frames")
    y = np.concatenate(out) if out else np.zeros(0, np.int16)
    del out
    keep, contiguous = trim_target(len(y), gap)
    y = y[:keep]
    info["contiguous_to_next"] = contiguous
    info["gap_to_next_s"] = 0.0 if (contiguous or gap is None) else round(gap - len(y) / SR, 4)
    info["decode_resample_s"] = time.perf_counter() - t1
    n_kept = min(n_in, count_limit)
    info["peak"] = peak
    zeros_per_s = np.concatenate(zps) if zps else np.zeros(0, np.int32)
    samples_per_s = np.concatenate(sps) if sps else np.zeros(0, np.int32)
    info["zero_frac"] = int(zeros_per_s.sum()) / max(n_kept, 1)
    info["clip_frac"] = clips / max(n_kept, 1)
    expected = round(n_kept * SR / sr)
    if abs(len(y) - expected) > SR // 10:
        info["flags"].append(f"resampled length {len(y)} vs expected {expected}")
    return info, y, zeros_per_s, samples_per_s


# ---------------------------------------------------------------- accumulation

class DayAccumulator:
    def __init__(self):
        self.t, self.scores, self.files = [], [], []
        self.emb_sum = defaultdict(lambda: np.zeros(1280, np.float64))
        self.band_sum = defaultdict(lambda: np.zeros(len(BANDS), np.float64))
        self.n = defaultdict(int)
        self.zeros = self.samples = 0
        self.stretches = 0           # continuous stretches that produced windows
        self.dropped_tail_s = 0.0    # partial windows dropped at real gaps, midnight and the deployment end

    def add(self, t, scores, emb, bands):
        self.t.append(t)
        self.scores.append(scores)
        for b, e, p in zip((t // BLOCK_S).astype(int), emb, bands):
            self.emb_sum[b] += e
            self.band_sum[b] += p
            self.n[b] += 1


def completed_days(out_dir=OUT_DIR, log_path=DEFAULT_LOG):
    """Days already scored by this pipeline version into out_dir, whose .npz matches its logged sha256."""
    latest = {}
    rel = str(out_dir.relative_to(ROOT))
    for line in open(log_path, encoding="utf-8"):
        e = json.loads(line)
        d = e["details"]
        if (e["action"] == "score_day" and d.get("pipeline_version") == PIPELINE_VERSION
                and str(d.get("npz", "")).startswith(rel + "/")):
            latest[d["day"]] = d
    done = {}
    for day, rep in latest.items():
        path = ROOT / rep["npz"]
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == rep["sha256"]:
            done[day] = rep
    return done


def git_commit(allow_dirty):
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "src"], cwd=ROOT, capture_output=True,
                           text=True, check=True).stdout.strip()
    if dirty and not allow_dirty:
        raise SystemExit(f"src/ has uncommitted changes; commit first (or --allow-dirty):\n{dirty}")
    return head + ("-dirty" if dirty else "")


# ---------------------------------------------------------------- main

def main(actor, workers, limit, skip_existing, days_csv, out_dir, allow_dirty):
    commit = git_commit(allow_dirty)
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    import tensorflow as tf

    gpus = tf.config.list_physical_devices("GPU")
    for g in gpus:
        tf.config.experimental.set_memory_growth(g, True)
    model = tf.saved_model.load(str(MODEL_DIR))
    meta = model.metadata()
    classes = [c.decode() for c in meta["class_names"].numpy()]
    assert int(meta["input_sample_rate"]) == SR and int(meta["context_width_samples"]) == WIN
    hann, bw = band_weights()
    hann_t, bw_t = tf.constant(hann), tf.constant(bw)

    @tf.function
    def run(w):
        sp = model.front_end(w)[:, CROP[0]:CROP[1]]
        x = w[..., 0] * hann_t
        p = tf.math.square(tf.abs(tf.signal.rfft(x)))
        return tf.sigmoid(model.logits(sp)), model.features(sp), tf.matmul(p, bw_t)

    days = select_days(days_csv)
    if limit:
        days = days.head(limit)
    resumed = []
    if skip_existing:
        prior = completed_days(out_dir)
        keys = days["site"] + "_" + days["deployment"] + "_" + days["date"]
        resumed = [prior[k] for k in keys if k in prior]
        days = days[~keys.isin(prior)]
    selected = set(days["site"] + "_" + days["deployment"] + "_" + days["date"])
    listing = json.loads(LISTING_PATH.read_text())
    tasks = plan_tasks(days, listing)
    remaining = defaultdict(int)
    for t in tasks:
        for d in t["days"]:
            remaining[d] += 1
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = {"pipeline_version": PIPELINE_VERSION, "git_commit": commit}
    log_event(actor, "score_start", {
        **stamp, "days": len(days), "files": len(tasks), "workers": workers,
        "gpu": [g.name for g in gpus], "days_csv": str(days_csv.relative_to(ROOT)),
        "out_dir": str(out_dir.relative_to(ROOT)), "model_dir": str(MODEL_DIR.relative_to(ROOT)),
        "resampler": "soxr VHQ 48000->24000", "window_samples": WIN, "block_s": BLOCK_S,
        "bands_hz": [[lo, hi] for _, lo, hi in BANDS], "audio_saved_to_disk": False,
        "skipped_existing": len(resumed)})

    acc = defaultdict(DayAccumulator)
    saved = set()
    stream = {}  # key -> {"name", "carry", "carry_t0"} for the file just processed
    gpu_s, n_windows, day_reports = 0.0, 0, []
    day_t0 = {}

    def score(dkey, off, piece):
        nonlocal gpu_s, n_windows
        n = len(piece) // WIN
        if not n:
            return
        w = piece[: n * WIN].reshape(n, WIN)
        sc, em, bp = [], [], []
        g0 = time.perf_counter()
        for i in range(0, n, BATCH):
            xb = (w[i:i + BATCH].astype(np.float32) / 32768.0)[..., None]
            s, e, p = run(tf.constant(xb))
            sc.append(s.numpy())
            em.append(e.numpy())
            bp.append(p.numpy())
        gpu_s += time.perf_counter() - g0
        n_windows += n
        acc[dkey].add(off + WIN_S * np.arange(n), np.concatenate(sc), np.concatenate(em), np.concatenate(bp))

    def process(task, info, y, zps, sps):
        key, start = task["key"], datetime.fromisoformat(task["start"])
        prev = stream.get(key)
        t0 = start
        # Stitched: the previous file in the listing was processed and reached this file's start exactly.
        stitched = bool(prev and prev["name"] == task["prev_name"] and prev["contiguous"])
        if stitched and len(prev["carry"]):
            y = np.concatenate([prev["carry"], y])
            t0 = prev["carry_t0"]
        elif prev and not stitched and len(prev["carry"]) and prev["day"] in acc:
            acc[prev["day"]].dropped_tail_s += len(prev["carry"]) / SR  # next processed file is not adjacent
        for date, n_z in zeros_by_day(start, zps, sps).items():
            dkey = f"{key}_{date}"
            if dkey in selected and dkey not in saved:
                acc[dkey].zeros += n_z[0]
                acc[dkey].samples += n_z[1]
        pieces = list(day_pieces(t0, len(y)))
        carry, carry_t0, carry_day = np.zeros(0, np.int16), None, None
        for j, (date, off, i0, i1) in enumerate(pieces):
            dkey = f"{key}_{date}"
            piece = y[i0:i1]
            n = len(piece) // WIN
            tail = piece[n * WIN:]
            last = j == len(pieces) - 1
            if last and info["contiguous_to_next"]:
                carry, carry_day = tail, dkey
                carry_t0 = t0 + timedelta(seconds=(i0 + n * WIN) / SR)
            elif dkey in selected and dkey not in saved:
                acc[dkey].dropped_tail_s += len(tail) / SR
            if dkey in selected and dkey not in saved:
                if n:
                    acc[dkey].stretches += int(j > 0 or not stitched)  # new grid at midnight or after a gap
                score(dkey, off, piece)
                acc[dkey].files.append({**info, "piece_offset_s": off, "piece_windows": n,
                                        "stitched_from_prev": stitched and j == 0})
        stream[key] = {"name": task["name"], "carry": carry, "carry_t0": carry_t0, "day": carry_day,
                       "contiguous": info["contiguous_to_next"]}
        for dkey in task["days"]:
            remaining[dkey] -= 1
            if remaining[dkey] == 0:
                day_reports.append(save_day(dkey, acc.pop(dkey, DayAccumulator()), classes,
                                            time.perf_counter() - day_t0[dkey], actor, out_dir, stamp))
                saved.add(dkey)

    T0 = time.perf_counter()
    ctx = mp.get_context("spawn")
    with cf.ProcessPoolExecutor(workers, mp_context=ctx) as pool:
        pending, ready, nxt, it = {}, {}, 0, iter(enumerate(tasks))

        def refill():
            while len(pending) + len(ready) < workers + 1:
                item = next(it, None)
                if item is None:
                    return
                i, t = item
                for d in t["days"]:
                    day_t0.setdefault(d, time.perf_counter())
                pending[pool.submit(decode_task, t)] = i

        refill()
        while pending or ready:
            if pending:
                done, _ = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
                for fut in done:
                    ready[pending.pop(fut)] = fut.result()
            while nxt in ready:  # strict time order, so stitching sees files in sequence
                process(tasks[nxt], *ready.pop(nxt))
                nxt += 1
            refill()
    total = time.perf_counter() - T0
    summary = {**stamp, "days": len(day_reports), "windows": n_windows, "total_s": round(total, 1),
               "gpu_s": round(gpu_s, 1), "gpu_windows_per_s": round(n_windows / gpu_s, 1) if gpu_s else None,
               "end_to_end_windows_per_s": round(n_windows / total, 1),
               "mean_s_per_day": round(total / max(len(day_reports), 1), 1),
               "flagged_days": [r["day"] for r in resumed + day_reports if r["flags"]],
               "zero_flag_days": [r["day"] for r in resumed + day_reports if r["zero_flag"]]}
    if resumed:
        # Timing fields above cover this run only; resumed days come from their audit-log entries.
        summary["resumed_days"] = len(resumed)
        summary["total_days"] = len(resumed) + len(day_reports)
    (out_dir / "run_report.json").write_text(
        json.dumps({"summary": summary, "days": resumed + day_reports}, indent=1))
    log_event(actor, "score_end", summary)
    print(json.dumps(summary, indent=1))


def save_day(dkey, a: DayAccumulator, classes, wall_s, actor, out_dir, stamp):
    if a.t:
        t = np.concatenate(a.t)
        sc = np.concatenate(a.scores).astype(np.float32)
        order = np.argsort(t, kind="stable")
        t, sc = t[order], sc[order]
    else:
        t, sc = np.zeros(0), np.zeros((0, len(classes)), np.float32)
    blocks = np.array(sorted(a.n), dtype=np.int32)
    bn = np.array([a.n[b] for b in blocks], dtype=np.int32)
    emb = (np.stack([a.emb_sum[b] / a.n[b] for b in blocks]).astype(np.float16) if len(blocks)
           else np.zeros((0, 1280), np.float16))
    with np.errstate(divide="ignore"):
        band_db = (10 * np.log10(np.stack([a.band_sum[b] / a.n[b] for b in blocks])).astype(np.float32)
                   if len(blocks) else np.zeros((0, len(BANDS)), np.float32))
    hb = sc[:, classes.index("Mn")] if len(sc) else np.zeros(0, np.float32)
    zero_fraction = a.zeros / a.samples if a.samples else None

    flags = sorted({f for fi in a.files for f in fi["flags"]})
    hours = len(t) * WIN_S / 3600
    if hours < 20:
        flags.append(f"only {hours:.2f} h of windows")
    if len(t) and (np.diff(t) < WIN_S - 1e-6).any():
        flags.append("overlapping windows")
    if not np.isfinite(sc).all():
        flags.append("non-finite scores")
    if not np.isfinite(band_db).all():
        flags.append("non-finite band levels")
    if any(fi["peak"] == 0 for fi in a.files):
        flags.append("a file is all zeros")
    if zero_fraction is not None and zero_fraction > ZERO_FLAG:
        flags.append(f"zero_fraction {zero_fraction:.4f} > {ZERO_FLAG}")
    if any(fi["clip_frac"] > 0.001 for fi in a.files):
        flags.append("a file has >0.1% clipped samples")
    gaps = np.diff(t)
    big_gaps = int((gaps > WIN_S + 60).sum()) if len(t) else 0
    if big_gaps:
        flags.append(f"{big_gaps} gap(s) >1 min between windows")

    path = out_dir / f"{dkey}.npz"
    np.savez_compressed(path, window_start_s=t, scores=sc, class_names=np.array(classes), humpback=hb,
                        block_start_s=blocks * BLOCK_S, block_emb=emb, block_n_windows=bn,
                        block_band_db=band_db, band_names=np.array([b[0] for b in BANDS]),
                        band_edges_hz=np.array([[lo, hi] for _, lo, hi in BANDS], np.float32),
                        zero_fraction=np.float64(np.nan if zero_fraction is None else zero_fraction),
                        pipeline_version=np.array(stamp["pipeline_version"]),
                        git_commit=np.array(stamp["git_commit"]),
                        files=np.array(json.dumps(a.files)))
    rep = {**stamp, "day": dkey, "windows": int(len(t)), "hours": round(hours, 3), "files": len(a.files),
           "wall_s": round(wall_s, 1), "blocks": int(len(blocks)), "stretches": a.stretches,
           "dropped_tail_s": round(a.dropped_tail_s, 3),
           "zero_fraction": zero_fraction, "zero_flag": bool(zero_fraction is not None and zero_fraction > ZERO_FLAG),
           "humpback_median": float(np.median(hb)) if len(hb) else None,
           "humpback_max": float(hb.max()) if len(hb) else None,
           "min_peak": min(fi["peak"] for fi in a.files) if a.files else None,
           "flags": flags, "npz": str(path.relative_to(ROOT)),
           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    log_event(actor, "score_day", rep)
    print(dkey, rep["windows"], rep["hours"], rep["wall_s"], flags, flush=True)
    return rep


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--actor", required=True)
    p.add_argument("--days", default=str(DAYS_CSV), help="day list CSV; only split == trainval rows are used")
    p.add_argument("--out", default=str(OUT_DIR))
    p.add_argument("--workers", type=int, default=5)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--skip-existing", action="store_true",
                   help="resume: skip days whose .npz matches their logged sha256 (same version and out dir)")
    p.add_argument("--allow-dirty", action="store_true", help="run with uncommitted src/ changes (testing only)")
    a = p.parse_args()
    from pathlib import Path
    main(a.actor, a.workers, a.limit, a.skip_existing, Path(a.days).resolve(), Path(a.out).resolve(),
         a.allow_dirty)
