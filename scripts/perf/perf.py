#!/usr/bin/env python3
"""Performance gate tooling for nty (standard library only).

Subcommands:

  measure  Measure one binary and write a JSON result file.
  compare  Check a head result against the budgets and against a baseline
           result; print a Markdown table (also appended to
           $GITHUB_STEP_SUMMARY when set). Exits 1 on any failure.
  noise    Measure the same binary repeatedly and report the spread of each
           metric (max-min relative to the median, and the coefficient of
           variation).

Metrics:

  binary_size_bytes   File size of the stripped release binary.
  startup_ms          Median wall time of `nty --version` (hyperfine, no shell).
  interactive_ms      Median time from spawning `nty` in a pseudo-terminal until
                      the input prompt is rendered (POSIX only).
  idle_rss_bytes      Resident set size after the prompt has been idle for
                      --idle seconds (POSIX only).

Startup and interactive timings exclude the network by construction: the
binary under test makes no network requests on these paths.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

MIB = 1024 * 1024

# Budgets from the design's performance section (strict tier).
BUDGETS = {
    "binary_size_bytes": 25 * MIB,
    "startup_ms": 50.0,
    "interactive_ms": 50.0,
    "idle_rss_bytes": 30 * MIB,
}

# Maximum allowed regression of head relative to the baseline.
REGRESSION_LIMIT = 0.10

# Timing metrics are noisy on macOS and Windows runners (same-commit spread of
# 50% or more), so their regressions are only gated on Linux, and only when the
# absolute change also exceeds this floor. Budgets are checked everywhere.
TIMING_METRICS = {"startup_ms", "interactive_ms"}
TIMING_FLOOR_MS = 0.5

PROMPT = b"> "


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# measurement
# --------------------------------------------------------------------------


def measure_startup(binary: str, runs: int, warmup: int) -> dict:
    hyperfine = shutil.which("hyperfine")
    if hyperfine is None:
        raise SystemExit("hyperfine not found on PATH")
    # With --shell=none, hyperfine splits the command with POSIX shell-word
    # rules, which treat backslashes as escapes. Windows accepts forward
    # slashes, so normalise the path and quote it.
    command = '"{}" --version'.format(binary.replace("\\", "/"))
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "hf.json")
        subprocess.run(
            [
                hyperfine,
                "--shell=none",
                "--warmup", str(warmup),
                "--runs", str(runs),
                "--export-json", out,
                "--style", "none",
                command,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        with open(out, encoding="utf-8") as f:
            data = json.load(f)
    # hyperfine 2.x export format (schema version 2).
    summary = data["results"][0]["summary"]
    result = {"startup_ms": summary["time_wall_clock"]["median"] * 1000.0}
    if "instructions" in summary:
        result["startup_instructions"] = summary["instructions"]["median"]
    return result


def rss_bytes(pid: int) -> int:
    status = f"/proc/{pid}/status"
    if os.path.exists(status):
        with open(status, encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
        raise RuntimeError("VmRSS not found")
    out = subprocess.check_output(["ps", "-o", "rss=", "-p", str(pid)], text=True)
    return int(out.strip()) * 1024


def measure_interactive_once(binary: str, idle: float, timeout: float) -> tuple[float, int]:
    import pty  # POSIX only
    import select

    start = time.perf_counter()
    pid, fd = pty.fork()
    if pid == 0:  # child
        try:
            os.execv(binary, [binary])
        finally:
            os._exit(127)
    try:
        buf = b""
        ready_at = None
        deadline = start + timeout
        while ready_at is None:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise RuntimeError(f"prompt not seen within {timeout}s; output={buf!r}")
            r, _, _ = select.select([fd], [], [], remaining)
            if not r:
                continue
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                chunk = b""
            if not chunk:
                raise RuntimeError(f"process exited before the prompt; output={buf!r}")
            buf += chunk
            if PROMPT in buf:
                ready_at = time.perf_counter()
        time.sleep(idle)
        rss = rss_bytes(pid)
        os.write(fd, b"\n")
        return (ready_at - start) * 1000.0, rss
    finally:
        for _ in range(50):
            done, _status = os.waitpid(pid, os.WNOHANG)
            if done:
                break
            time.sleep(0.02)
        else:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        os.close(fd)


def measure_interactive(binary: str, runs: int, idle: float, timeout: float) -> dict:
    times, rss = [], []
    # One untimed warm-up run so the page cache state matches the startup test.
    measure_interactive_once(binary, 0.0, timeout)
    for i in range(runs):
        t, r = measure_interactive_once(binary, idle if i == 0 else 0.0, timeout)
        times.append(t)
        if i == 0:
            rss.append(r)
    return {"interactive_ms": statistics.median(times), "idle_rss_bytes": rss[0]}


def measure(args: argparse.Namespace) -> dict:
    binary = os.path.abspath(args.bin)
    result: dict = {
        "platform": f"{platform.system()}-{platform.machine()}",
        "binary_size_bytes": os.path.getsize(binary),
    }
    result.update(measure_startup(binary, args.runs, args.warmup))
    if os.name == "posix" and not args.no_pty:
        try:
            result.update(measure_interactive(binary, args.pty_runs, args.idle, args.timeout))
        except RuntimeError as e:
            # A baseline built from an older commit may predate the interactive
            # entry; the head must always provide it.
            if not args.pty_optional:
                raise
            log(f"interactive metrics unavailable for this binary: {e}")
    else:
        log("interactive metrics skipped (no POSIX pseudo-terminal support)")
    return result


def cmd_measure(args: argparse.Namespace) -> int:
    result = measure(args)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)
    return 0


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------


def fmt(metric: str, value) -> str:
    if value is None:
        return "—"
    if metric.endswith("_bytes"):
        return f"{value / MIB:.2f} MiB"
    if metric.endswith("_ms"):
        return f"{value:.2f} ms"
    return f"{value:,.0f}"


GATED = ["binary_size_bytes", "startup_ms", "interactive_ms", "idle_rss_bytes"]
INFO = ["startup_instructions"]


def cmd_compare(args: argparse.Namespace) -> int:
    with open(args.head, encoding="utf-8") as f:
        head = json.load(f)
    base = None
    if args.base:
        with open(args.base, encoding="utf-8") as f:
            base = json.load(f)

    failures = []
    rows = []
    for metric in GATED + INFO:
        h = head.get(metric)
        if h is None:
            continue
        b = base.get(metric) if base else None
        budget = BUDGETS.get(metric)
        delta = (h - b) / b if b else None
        regression_gated = metric in GATED and (
            metric not in TIMING_METRICS
            or (head.get("platform", "").startswith("Linux") and h - b > TIMING_FLOOR_MS)
        ) if b else False
        status = "✅"
        if budget is not None and h > budget:
            status = "❌ over budget"
            failures.append(f"{metric}: {fmt(metric, h)} exceeds budget {fmt(metric, budget)}")
        elif regression_gated and delta is not None and delta > REGRESSION_LIMIT:
            status = "❌ regression"
            failures.append(
                f"{metric}: {fmt(metric, h)} is {delta:+.1%} vs baseline {fmt(metric, b)}"
                f" (limit +{REGRESSION_LIMIT:.0%})"
            )
        elif metric in INFO:
            status = "ℹ️ info"
        elif metric in TIMING_METRICS and b and not regression_gated:
            status = "✅ (Δ not gated)"
        rows.append(
            f"| `{metric}` | {fmt(metric, b)} | {fmt(metric, h)} | "
            f"{'—' if delta is None else f'{delta:+.1%}'} | {fmt(metric, budget)} | {status} |"
        )

    title = args.title or f"Performance ({head.get('platform', '?')})"
    lines = [
        f"### {title}",
        "",
        "| Metric | Baseline | Head | Δ | Budget | Status |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
    ]
    if failures:
        lines += ["**Failed:**", "", *[f"- {x}" for x in failures], ""]
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report + "\n")
    for x in failures:
        log(f"perf gate: {x}")
    return 1 if failures else 0


def cmd_ab(args: argparse.Namespace) -> int:
    """Interleaved A/B measurement of a baseline and a head binary.

    Runner performance drifts within a job (thermal state, noisy neighbours,
    background services). Measuring all of the baseline first and all of the
    head afterwards turns that drift into a fake regression. Alternating the
    two in an ABBA order over several rounds and taking the per-metric median
    over rounds cancels linear drift and damps outliers.
    """
    bins = {"base": os.path.abspath(args.base_bin), "head": os.path.abspath(args.head_bin)}
    rounds: dict[str, list[dict]] = {"base": [], "head": []}

    def orders():
        for i in range(args.rounds):
            yield i, (["base", "head"] if i % 2 == 0 else ["head", "base"])

    # Phase 1: startup timings only, back to back, so that no idle period
    # (which lets the CPU clock down) separates the two binaries.
    for i, order in orders():
        for which in order:
            log(f"ab: startup round {i + 1}/{args.rounds}, {which}")
            r = {"platform": f"{platform.system()}-{platform.machine()}",
                 "binary_size_bytes": os.path.getsize(bins[which])}
            r.update(measure_startup(bins[which], args.runs, args.warmup))
            rounds[which].append(r)
    # Phase 2: interactive timings and idle memory.
    if os.name == "posix" and not args.no_pty:
        for i, order in orders():
            for which in order:
                log(f"ab: interactive round {i + 1}/{args.rounds}, {which}")
                try:
                    rounds[which][i].update(
                        measure_interactive(bins[which], args.pty_runs, args.idle, args.timeout)
                    )
                except RuntimeError as e:
                    # Only the baseline may predate the interactive entry.
                    if which == "head":
                        raise
                    log(f"interactive metrics unavailable for the baseline: {e}")
    for which, out in (("base", args.base_out), ("head", args.head_out)):
        merged: dict = {"platform": rounds[which][0]["platform"], "rounds": args.rounds}
        keys = {k for r in rounds[which] for k, v in r.items() if isinstance(v, (int, float))}
        for k in sorted(keys):
            vals = [r[k] for r in rounds[which] if k in r]
            if len(vals) == len(rounds[which]):
                merged[k] = statistics.median(vals)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, sort_keys=True)
            f.write("\n")
        print(json.dumps({which: merged}, sort_keys=True))
    return 0


def cmd_noise(args: argparse.Namespace) -> int:
    samples: dict[str, list[float]] = {}
    for i in range(args.repeat):
        log(f"noise: repetition {i + 1}/{args.repeat}")
        for k, v in measure(args).items():
            if isinstance(v, (int, float)):
                samples.setdefault(k, []).append(float(v))
    report = {"platform": f"{platform.system()}-{platform.machine()}", "repeat": args.repeat}
    lines = [
        f"### Measurement noise ({report['platform']}, {args.repeat} repetitions)",
        "",
        "| Metric | Median | Min | Max | (max−min)/median | CV |",
        "|---|---|---|---|---|---|",
    ]
    for k, vs in samples.items():
        med = statistics.median(vs)
        spread = (max(vs) - min(vs)) / med if med else 0.0
        cv = statistics.stdev(vs) / statistics.mean(vs) if len(vs) > 1 and statistics.mean(vs) else 0.0
        report[k] = {"median": med, "min": min(vs), "max": max(vs), "spread": spread, "cv": cv}
        lines.append(
            f"| `{k}` | {fmt(k, med)} | {fmt(k, min(vs))} | {fmt(k, max(vs))} | {spread:.1%} | {cv:.1%} |"
        )
    text = "\n".join(lines) + "\n"
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, sort_keys=True)
            f.write("\n")
    return 0


def main() -> int:
    # Reports contain non-ASCII symbols; Windows consoles default to a legacy
    # code page that cannot encode them.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_measure_args(sp, need_bin=True):
        if need_bin:
            sp.add_argument("--bin", required=True, help="path to the nty binary")
        sp.add_argument("--runs", type=int, default=50, help="hyperfine runs (default 50)")
        sp.add_argument("--warmup", type=int, default=5)
        sp.add_argument("--pty-runs", type=int, default=20, help="interactive runs (default 20)")
        sp.add_argument("--idle", type=float, default=5.0, help="idle seconds before sampling RSS")
        sp.add_argument("--timeout", type=float, default=10.0, help="seconds to wait for the prompt")
        sp.add_argument("--no-pty", action="store_true", help="skip interactive metrics")
        sp.add_argument(
            "--pty-optional",
            action="store_true",
            help="record no interactive metrics instead of failing when the prompt never appears",
        )
        sp.add_argument("--out", help="write JSON here")

    m = sub.add_parser("measure", help="measure one binary")
    add_measure_args(m)
    m.set_defaults(func=cmd_measure)

    c = sub.add_parser("compare", help="gate head against budgets and a baseline")
    c.add_argument("--head", required=True)
    c.add_argument("--base")
    c.add_argument("--title")
    c.set_defaults(func=cmd_compare)

    n = sub.add_parser("noise", help="repeat measurements and report the spread")
    add_measure_args(n)
    n.add_argument("--repeat", type=int, default=10)
    n.set_defaults(func=cmd_noise)

    ab = sub.add_parser("ab", help="interleaved baseline/head measurement (ABBA rounds)")
    add_measure_args(ab, need_bin=False)
    ab.add_argument("--base-bin", required=True)
    ab.add_argument("--head-bin", required=True)
    ab.add_argument("--base-out", required=True)
    ab.add_argument("--head-out", required=True)
    ab.add_argument("--rounds", type=int, default=6)
    ab.set_defaults(runs=60, warmup=20, pty_runs=10)
    ab.set_defaults(func=cmd_ab, bin=None)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
