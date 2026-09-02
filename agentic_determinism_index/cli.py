import argparse
import datetime
import hashlib
import json
import os
import platform
import sys

from . import __version__
from .probe import assert_no_tool_cases, run_probe, utcnow
from .providers import make_provider
from .report import markdown, score_run
from .site import build_payload, latest_scored_run, render_html
from .watch import format_tick_summary, run_tick


def _load(path):
    with open(path) as f:
        return json.load(f)


def _sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def cmd_run(args):
    config = _load(args.config)
    cases = _load(args.cases)["cases"]
    assert_no_tool_cases(cases)
    watch_dir = getattr(args, "watch_dir", "runs/watch")

    if getattr(args, "due_only", False):
        from .watch import filter_score_due_targets
        due, skipped = filter_score_due_targets(config.get("targets") or [], watch_dir)
        for s in skipped:
            print(
                f"skip score {s['target']}: not due "
                f"(byte_exact={s.get('byte_exact')})",
                flush=True,
            )
        config = dict(config)
        config["targets"] = due
        if not due:
            print("no targets due for full score; watch-only cadence applies")
            return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    run_dir = os.path.join(args.out, stamp)
    os.makedirs(os.path.join(run_dir, "probes"), exist_ok=True)

    manifest = {
        "harness_version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "config_sha256": _sha256_file(args.config),
        "cases_sha256": _sha256_file(args.cases),
        "burst": args.burst,
        "serial": args.serial,
        "gap_s": args.gap,
        "due_only": bool(getattr(args, "due_only", False)),
        "started": utcnow(),
    }
    for target in config["targets"]:
        key_env = target.get("api_key_env")
        if key_env and not os.environ.get(key_env):
            print(f"skip {target['provider']}/{target.get('model')}: "
                  f"{key_env} not set", flush=True)
            continue
        provider = make_provider(target)
        for case in cases:
            label = f"{target['provider']}/{target['model']} case={case['id']}"
            print(f"probing {label} (burst={args.burst}, serial={args.serial})",
                  flush=True)
            samples = run_probe(provider, case, args.burst, args.serial, args.gap)
            errors = sum(1 for s in samples if s.get("error"))
            if errors:
                print(f"  {errors}/{len(samples)} requests errored", flush=True)
            name = "{}__{}__{}.json".format(
                target["provider"], target["model"].replace("/", "-"), case["id"])
            # Same model probed under different pins (OpenRouter provider
            # prefs, NIM force_deterministic) must not overwrite each other.
            pin = target.get("label") or ""
            if not pin:
                prefs = target.get("provider_prefs") or {}
                order = prefs.get("order") or prefs.get("only") or []
                if order:
                    pin = "via-" + "-".join(str(x) for x in order)
                elif target.get("force_deterministic"):
                    pin = "force-det"
            if pin:
                safe = "".join(c if c.isalnum() or c in "-_" else "-"
                               for c in pin.lower()).strip("-")
                name = "{}__{}__{}__{}.json".format(
                    target["provider"], target["model"].replace("/", "-"),
                    safe, case["id"])
            with open(os.path.join(run_dir, "probes", name), "w") as f:
                json.dump({
                    "target": {k: v for k, v in target.items()
                               if k != "api_key_env"},
                    "case": case,
                    "request": provider.describe_request(case),
                    "samples": samples,
                }, f, indent=1)
    manifest["finished"] = utcnow()
    with open(os.path.join(run_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print(run_dir)


def cmd_score(args):
    rows = score_run(args.run_dir)
    if not rows:
        print(f"no probes found under {args.run_dir}/probes/", file=sys.stderr)
        return 1
    with open(os.path.join(args.run_dir, "scores.json"), "w") as f:
        json.dump(rows, f, indent=1)
    md = markdown(rows)
    with open(os.path.join(args.run_dir, "SCORES.md"), "w") as f:
        f.write(md)
    # Feed watch state so non-byte-exact tuples are not re-scored often.
    try:
        from .watch import ingest_score_hints
        ingest_score_hints(
            getattr(args, "watch_dir", "runs/watch"),
            rows,
            run_stamp=os.path.basename(os.path.abspath(args.run_dir)),
        )
    except Exception as e:
        print(f"note: score hints not written ({e})", file=sys.stderr)
    print(md, end="")
    return 0


def cmd_site(args):
    run_dir = args.run
    if not run_dir:
        run_dir = latest_scored_run(args.run_root)

    if run_dir and not os.path.isdir(run_dir):
        print(f"run directory not found: {run_dir}", file=sys.stderr)
        return 1
    if not run_dir:
        print(
            f"note: no scored run under {args.run_root}; "
            "building page without leaderboard rows",
            file=sys.stderr,
        )

    from .site import write_site

    paths = write_site(
        out_html=args.out,
        run_dir=run_dir,
        run_root=args.run_root,
        watch_dir=args.watch_dir,
    )
    for p in paths:
        print(p)
    return 0


def cmd_watch(args):
    cfg = {}
    if args.min_interval is not None:
        cfg["min_interval_s"] = args.min_interval
    if args.max_interval is not None:
        cfg["max_interval_s"] = args.max_interval
    if args.backoff is not None:
        cfg["backoff"] = args.backoff
    if args.stable_after is not None:
        cfg["stable_after"] = args.stable_after
    if args.jitter is not None:
        cfg["jitter"] = args.jitter

    if not os.path.isfile(args.config):
        print(
            f"watch config not found: {args.config}\n"
            f"Copy configs/watch.example.json → configs/watch.json and enable targets.",
            file=sys.stderr,
        )
        return 1

    summary = run_tick(
        config_path=args.config,
        cases_path=args.cases,
        watch_dir=args.out,
        force=args.force,
        cfg=cfg,
    )
    sys.stdout.write(format_tick_summary(summary))
    if summary.get("drift_events"):
        return 2  # non-zero so CI can notify on drift without failing hard callers
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="agentic-determinism-index",
        description="Measure how reproducible hosted LLM APIs actually are.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    runp = sub.add_parser("run", help="fire probes and record raw transcripts")
    runp.add_argument("--config", required=True, help="targets config (JSON)")
    runp.add_argument("--cases", default="cases/default/cases.json")
    runp.add_argument("--out", default="runs/reference")
    runp.add_argument("--burst", type=int, default=10,
                      help="concurrent identical requests per case")
    runp.add_argument("--serial", type=int, default=3,
                      help="spaced identical requests per case")
    runp.add_argument("--gap", type=int, default=60,
                      help="seconds between serial requests")
    runp.add_argument(
        "--due-only",
        action="store_true",
        help="only score targets whose watch state says a full re-score is due "
             "(byte-exact ~daily; non-exact ~monthly)",
    )
    runp.add_argument(
        "--watch-dir",
        default="runs/watch",
        help="watch state dir used by --due-only and score hints",
    )
    runp.set_defaults(fn=cmd_run)

    scorep = sub.add_parser("score", help="score a run directory from its transcripts")
    scorep.add_argument("run_dir")
    scorep.add_argument("--watch-dir", default="runs/watch",
                        help="where to write score cadence hints")
    scorep.set_defaults(fn=cmd_score)

    sitep = sub.add_parser("site", help="build a static leaderboard website")
    sitep.add_argument("--run", help="reference run directory")
    sitep.add_argument("--run-root", default="runs/reference")
    sitep.add_argument("--watch-dir", default="runs/watch",
                       help="stack-watch history dir (optional drift panel)")
    sitep.add_argument("--out", default="website/index.html")
    sitep.set_defaults(fn=cmd_site)

    watchp = sub.add_parser(
        "watch",
        help="cheap stack-ID tick with adaptive backoff (not a full score run)",
    )
    watchp.add_argument("--config", default="configs/watch.json")
    watchp.add_argument("--cases", default="cases/watch/cases.json")
    watchp.add_argument("--out", default="runs/watch",
                        help="watch state + history directory")
    watchp.add_argument("--force", action="store_true",
                        help="probe all targets even if not due")
    watchp.add_argument("--min-interval", type=int, default=None,
                        help="seconds (default 3600)")
    watchp.add_argument("--max-interval", type=int, default=None,
                        help="seconds (default 86400)")
    watchp.add_argument("--backoff", type=float, default=None,
                        help="multiplier after stable streak (default 1.5)")
    watchp.add_argument("--stable-after", type=int, default=None,
                        help="unchanged ticks before backoff (default 3)")
    watchp.add_argument("--jitter", type=float, default=None,
                        help="fractional jitter on due time (default 0.20)")
    watchp.set_defaults(fn=cmd_watch)

    args = ap.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
