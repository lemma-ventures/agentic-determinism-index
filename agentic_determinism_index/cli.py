import argparse
import datetime
import hashlib
import json
import os
import platform
import sys

from . import __version__
from .probe import run_probe, utcnow
from .providers import make_provider
from .report import markdown, score_run
from .site import build_payload, latest_scored_run, render_html


def _load(path):
    with open(path) as f:
        return json.load(f)


def _sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def cmd_run(args):
    config = _load(args.config)
    cases = _load(args.cases)["cases"]
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
    print(md, end="")
    return 0


def cmd_site(args):
    if args.run:
        run_dir = args.run
    else:
        run_dir = latest_scored_run(args.run_root)
        if not run_dir:
            print(f"no scored run found under {args.run_root}", file=sys.stderr)
            return 1

    if not os.path.isdir(run_dir):
        print(f"run directory not found: {run_dir}", file=sys.stderr)
        return 1

    payload = build_payload(run_dir)
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w") as f:
        f.write(render_html(payload))
    print(args.out)
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
    runp.set_defaults(fn=cmd_run)

    scorep = sub.add_parser("score", help="score a run directory from its transcripts")
    scorep.add_argument("run_dir")
    scorep.set_defaults(fn=cmd_score)

    sitep = sub.add_parser("site", help="build a static leaderboard website")
    sitep.add_argument("--run", help="reference run directory")
    sitep.add_argument("--run-root", default="runs/reference")
    sitep.add_argument("--out", default="website/index.html")
    sitep.set_defaults(fn=cmd_site)

    args = ap.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
