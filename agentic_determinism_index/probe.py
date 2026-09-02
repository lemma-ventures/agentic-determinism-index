"""Probe loop: fire N identical requests (concurrent burst + spaced serial)
and record raw samples. Transcripts keep the exact response text plus its
SHA-256 so published scores can be re-derived and verified."""
import concurrent.futures
import datetime
import hashlib
import time


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def one_call(provider, case, mode):
    rec = {"ts": utcnow(), "mode": mode}
    t0 = time.monotonic()
    try:
        r = provider.call(case)
        txt = r.get("text") or ""
        if not txt:
            rec["error"] = "unsupported: empty completion (tool call or similar)"
        else:
            rec.update(
                text=txt,
                sha256=sha256(txt),
                fingerprint=r.get("fingerprint"),
                model_version=r.get("model_version"),
            )
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    rec["latency_ms"] = round((time.monotonic() - t0) * 1000)
    return rec


def run_probe(provider, case, burst=10, serial=3, gap=60):
    samples = []
    if burst:
        with concurrent.futures.ThreadPoolExecutor(max_workers=burst) as ex:
            futures = [ex.submit(one_call, provider, case, "burst")
                       for _ in range(burst)]
            samples.extend(f.result() for f in futures)
    for i in range(serial):
        if i or burst:
            time.sleep(gap)
        samples.append(one_call(provider, case, "serial"))
    return samples
