"""Export a small, current-run metadata feed; never export article bodies/people.

Run after the legacy scraper under TZ=UTC. Its naive capture timestamp is
interpreted as UTC only within this explicitly declared collection window.
Legacy/NLP publication_date is not a publisher-verified publication timestamp.
"""
import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

UTC = timezone.utc
MAX_ROWS = 500
MAX_BYTES = 512 * 1024


def iso(value):
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except ValueError:
        return None


def clean(value, limit):
    return " ".join(str(value or "").split())[:limit]


def article_url(value):
    try:
        p = urlsplit(value)
        if p.scheme != "https" or not p.hostname or p.username or p.password or len(value) > 1500:
            return None
        # Reject malformed ports without following or fetching the URL.
        _ = p.port
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid")]
        return urlunsplit((p.scheme, p.netloc.lower(), p.path, urlencode(query), ""))
    except ValueError:
        return None


def build_snapshot(rows, started_at, now, revision):
    if started_at.tzinfo is None or now.tzinfo is None or started_at > now:
        raise ValueError("invalid_collection_window")
    selected = {}
    for row in rows:
        # The legacy CSV writes naive local timestamps. Only current-run rows
        # qualify, and the workflow explicitly runs the scraper with TZ=UTC.
        try:
            captured = datetime.strptime(row.get("date_scraped", ""), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except (ValueError, TypeError):
            continue
        if not started_at <= captured <= now:
            continue
        url = article_url(row.get("article_url", ""))
        headline = clean(row.get("headline"), 220)
        mentions = list(dict.fromkeys(clean(x, 100) for x in str(row.get("where", "")).split(";") if clean(x, 100)))[:20]
        if not url or not headline or not mentions:
            continue
        item = {"articleUrl": url, "headline": headline, "locationMentions": mentions,
                "capturedAt": iso(captured), "publishedAt": None,
                "publisher": urlsplit(url).hostname,
                "evidenceId": hashlib.sha256(url.encode()).hexdigest(),
                "dateBasis": "scraper_capture_time_not_publication"}
        if url not in selected or selected[url][0] < captured:
            selected[url] = (captured, item)
        if len(selected) > MAX_ROWS:
            oldest = min(selected, key=lambda key: selected[key][0])
            del selected[oldest]
    articles = [v[1] for v in sorted(selected.values(), key=lambda v: v[0], reverse=True)]
    result = {"schemaVersion": 1, "sourceRepository": "GO-Corporate-Executive-LSP/Crime-Scraper",
              "sourceRevision": revision, "generatedAt": iso(now), "collectionStartedAt": iso(started_at),
              "status": "candidates_available" if articles else "no_fresh_candidates",
              "clockBasis": "workflow_UTC_current_run_only", "articles": articles}
    while len(json.dumps(result, ensure_ascii=False).encode()) > MAX_BYTES:
        result["articles"].pop()
    if not result["articles"]:
        result["status"] = "no_fresh_candidates"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--started-at", required=True)
    args = parser.parse_args()
    started = timestamp(args.started_at)
    if not started or os.environ.get("TZ") != "UTC":
        raise ValueError("explicit_UTC_collection_window_required")
    csv.field_size_limit(8 * 1024 * 1024)
    with open(args.input, encoding="utf-8-sig", newline="") as source:
        snapshot = build_snapshot(csv.DictReader(source), started, datetime.now(UTC), os.environ.get("GITHUB_SHA", "manual"))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    temporary.replace(out)
    print(json.dumps({"status": snapshot["status"], "count": len(snapshot["articles"])}))


if __name__ == "__main__":
    main()
