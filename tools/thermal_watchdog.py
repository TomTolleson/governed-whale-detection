"""Thermal watchdog for frozen-pipeline scoring runs (Stage A). Lives OUTSIDE the frozen tree.

    python -m tools.thermal_watchdog --worktree <frozen worktree> --state-dir <dir> [--pause-c 85] [--resume]
                                     -- <arguments for `python -m src.pilot`>

What it does:
- Launches `python -m src.pilot <args>` inside the worktree (its own process group). With --resume it adds
  `--skip-existing`. It never changes any file in the worktree: nothing under src/ is touched, and the
  worktree's audit log is only ever READ (to see each finished day's `score_day` entry; plan A1).
- Every 15 s it records CPU Tctl (k10temp) and GPU temperature (nvidia-smi) to <state-dir>/thermal.csv.
- If CPU or GPU reaches --pause-c (85 C), or the CPU sensor fails 3 readings in a row, it requests a
  pause. The run is then stopped cleanly AFTER THE CURRENT DAY: as soon as the next `score_day` entry appears,
  the pilot's process group gets SIGTERM. Days still in progress are lost, and they are scored again on resume
  (`--skip-existing`; this is not a QA re-run).
- It never resumes by itself. After a pause it exits with code 3 and waits for the owner. Resuming is a new,
  manual invocation with --resume.
- Its own record is <state-dir>/events.jsonl (start, pause request, stop, exit) and pilot_stdout.log. A
  summary goes into the audit chain only afterwards, once the worktree log has been copied back.
Exit codes: 0 pilot finished cleanly; 3 thermal pause; 4 pilot failed; 5 stopped on a sensor failure.
"""
import argparse
import csv
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PERIOD_S = 15
SENSOR_FAILS = 3


def now():
    return datetime.now(timezone.utc).isoformat()


def read_tctl():
    for h in Path("/sys/class/hwmon").glob("hwmon*"):
        try:
            if (h / "name").read_text().strip() == "k10temp":
                return int((h / "temp1_input").read_text()) / 1000
        except OSError:
            pass
    return None


def read_gpu():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout.split()
        return float(out[0]) if out else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


class LogTail:
    """Read-only follower of the worktree audit log: counts new score_day entries."""

    def __init__(self, path):
        self.path, self.pos = Path(path), Path(path).stat().st_size
        self.days, self.buf = [], ""

    def poll(self):
        with open(self.path, "r", encoding="utf-8") as f:
            f.seek(self.pos)
            self.buf += f.read()
            self.pos = f.tell()
        *lines, self.buf = self.buf.split("\n")
        new = []
        for ln in lines:
            if ln.strip():
                e = json.loads(ln)
                if e["action"] == "score_day":
                    new.append(e["details"]["day"])
        self.days += new
        return new


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--pause-c", type=float, default=85.0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("pilot_args", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    wt = Path(a.worktree).resolve()
    state = Path(a.state_dir).resolve()
    if state == wt or wt in state.parents:
        raise SystemExit("refused: --state-dir must be outside the worktree")
    state.mkdir(parents=True, exist_ok=True)
    pargs = [x for x in a.pilot_args if x != "--"]
    if a.resume and "--skip-existing" not in pargs:
        pargs.append("--skip-existing")
    cmd = [a.python, "-m", "src.pilot", *pargs]
    wlog = wt / "audit_log.jsonl"
    events = state / "events.jsonl"

    def event(kind, **kw):
        with open(events, "a", encoding="utf-8") as f:
            f.write(json.dumps({"utc": now(), "event": kind, **kw}, sort_keys=True) + "\n")

    new_csv = not (state / "thermal.csv").exists()
    tcsv = open(state / "thermal.csv", "a", newline="")
    tw = csv.writer(tcsv)
    if new_csv:
        tw.writerow(["utc", "tctl_c", "gpu_c", "days_done_this_run", "pause_pending"])
    tail = LogTail(wlog)
    event("start", cmd=cmd, cwd=str(wt), pause_c=a.pause_c, resume=a.resume,
          worktree_log_lines_at_start=sum(1 for _ in open(wlog, encoding="utf-8")))
    out = open(state / "pilot_stdout.log", "a", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=wt, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    pending, fails, reason, code = None, 0, None, None
    while True:
        new = tail.poll()
        t, g = read_tctl(), read_gpu()
        fails = fails + 1 if t is None else 0
        tw.writerow([now(), t, g, len(tail.days), bool(pending)])
        tcsv.flush()
        if pending is None:
            if fails >= SENSOR_FAILS:
                pending = "sensor"
            elif (t is not None and t >= a.pause_c) or (g is not None and g >= a.pause_c):
                pending = "thermal"
            if pending:
                event("pause_requested", reason=pending, tctl_c=t, gpu_c=g, days_done_this_run=len(tail.days))
                new = []  # wait for the NEXT finished day
        rc = proc.poll()
        if rc is not None:
            tail.poll()
            code = 0 if rc == 0 else 4
            reason = "pilot_finished" if rc == 0 else f"pilot_exit_{rc}"
            break
        if pending and new:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=120)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            tail.poll()
            code = 3 if pending == "thermal" else 5
            reason = f"stopped_after_day ({pending})"
            event("stopped", reason=pending, after_day=new[-1], tctl_c=t, gpu_c=g)
            break
        time.sleep(2 if pending else PERIOD_S)  # once a pause is pending, watch for the day's end closely
    tcsv.close()
    out.close()
    event("exit", code=code, reason=reason, days_done_this_run=len(tail.days), last_day=(tail.days or [None])[-1],
          pilot_returncode=proc.returncode,
          worktree_log_lines_at_end=sum(1 for _ in open(wlog, encoding="utf-8")))
    print(json.dumps({"exit": code, "reason": reason, "days_done_this_run": len(tail.days)}), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
