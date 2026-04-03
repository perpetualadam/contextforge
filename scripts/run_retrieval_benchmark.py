#!/usr/bin/env python3
"""
Golden-set retrieval benchmarks against the API gateway.

Writes:
  - benchmark-results.json — machine-readable
  - benchmark-summary.md — human + CI job summary
  - report.html (optional) — self-contained static page

Exit codes:
  - 0 success
  - 2 threshold failure (--fail-under-mean-recall or --min-queries-passing)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests


def _recall_at_k(results: List[Dict[str, Any]], substrings: List[str], k: int) -> float:
    if not substrings:
        return 1.0
    top = results[:k]
    needles = [s.lower() for s in substrings]
    for r in top:
        fp = ((r.get("meta") or {}).get("file_path") or "").lower()
        text = (r.get("text") or "").lower()
        if any(n in fp or n in text for n in needles):
            return 1.0
    return 0.0


def run_one_query(
    gateway: str,
    item: Dict[str, Any],
    top_k: int,
    coarse: bool,
) -> Dict[str, Any]:
    q = item["q"]
    subs = item.get("relevant_file_substrings") or []
    ts = item.get("task_scope") or "general"
    payload = {
        "query": q,
        "top_k": top_k,
        "task_scope": ts,
        "expand_graph": ts not in ("", "general", None),
        "enable_reranking": False,
        "coarse_routing": coarse,
    }
    r = requests.post(
        f"{gateway.rstrip('/')}/search/vector",
        json=payload,
        timeout=120,
    )
    r.raise_for_status()
    out = r.json()
    results = out.get("results", [])
    inst = out.get("instrumentation") or {}
    lat = float(inst.get("total_ms", 0))
    rk = _recall_at_k(results, subs, top_k)
    return {
        "query": q,
        "task_scope": ts,
        "recall_at_k": rk,
        "latency_ms": lat,
        "num_results": len(results),
        "rerank_rank_delta": inst.get("rerank_rank_delta"),
    }


def run_golden_file(path: Path, gateway: str, top_k: int, coarse: bool) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for item in data.get("queries", []):
        rows.append(run_one_query(gateway, item, top_k, coarse))
    return rows


def _render_html(payload: Dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    table_rows = []
    for q in payload.get("per_query", []):
        cls = "ok" if q.get("recall_at_k", 0) >= 1 else "fail"
        table_rows.append(
            "<tr><td>{}</td><td class=\"{}\">{}</td><td>{}</td><td>{}</td></tr>".format(
                (q.get("query") or "")[:120],
                cls,
                q.get("recall_at_k"),
                q.get("latency_ms"),
                q.get("golden_set", ""),
            )
        )
    rows_html = "\n".join(table_rows)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>ContextForge retrieval benchmark</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 960px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }}
    th {{ background: #f4f4f4; }}
    .ok {{ color: #0a0; }} .fail {{ color: #a00; }}
  </style>
</head>
<body>
  <h1>Retrieval benchmark</h1>
  <p>Mean recall@k: <strong>{payload.get('mean_recall_at_k', 0):.4f}</strong> —
     Mean latency: <strong>{payload.get('mean_latency_ms', 0):.1f} ms</strong></p>
  <table>
    <tr><th>Query</th><th>Recall</th><th>Latency ms</th><th>Set</th></tr>
    {rows_html}
  </table>
  <h2>Raw JSON</h2>
  <pre id="raw"></pre>
  <script>
    const DATA = {data};
    document.getElementById('raw').textContent = JSON.stringify(DATA, null, 2);
  </script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gateway", default="http://localhost:8080")
    ap.add_argument("--golden", type=Path, help="Single golden JSON file")
    ap.add_argument(
        "--golden-dir",
        type=Path,
        help="Run all *.json in this directory",
    )
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--coarse", action="store_true")
    ap.add_argument("--output-dir", type=Path, help="Write benchmark-results.json + benchmark-summary.md")
    ap.add_argument("--fail-under-mean-recall", type=float, default=None)
    ap.add_argument("--min-queries-passing", type=int, default=0)
    ap.add_argument("--html", type=Path, help="Write self-contained HTML report")
    args = ap.parse_args()

    golden_files: List[Path] = []
    if args.golden:
        golden_files.append(args.golden)
    if args.golden_dir:
        golden_files.extend(sorted(args.golden_dir.glob("*.json")))

    if not golden_files:
        print("Specify --golden or --golden-dir", file=sys.stderr)
        return 1

    all_rows: List[Dict[str, Any]] = []
    for gf in golden_files:
        name = json.loads(gf.read_text(encoding="utf-8")).get("name", gf.stem)
        for row in run_golden_file(gf, args.gateway, args.top_k, args.coarse):
            row["golden_file"] = str(gf)
            row["golden_set"] = name
            all_rows.append(row)

    recalls = [r["recall_at_k"] for r in all_rows]
    lats = [r["latency_ms"] for r in all_rows]
    mean_recall = sum(recalls) / len(recalls) if recalls else 0.0
    mean_lat = sum(lats) / len(lats) if lats else 0.0
    passing = sum(1 for r in recalls if r >= 1.0)

    summary_lines = [
        "# Retrieval benchmark",
        "",
        f"- **When:** {datetime.now(timezone.utc).isoformat()}",
        f"- **Gateway:** `{args.gateway}`",
        f"- **Queries:** {len(all_rows)}",
        f"- **Mean recall@{args.top_k}:** {mean_recall:.4f}",
        f"- **Mean latency (ms):** {mean_lat:.1f}",
        f"- **Queries with full recall:** {passing}/{len(all_rows)}",
        "",
    ]
    for r in all_rows:
        summary_lines.append(
            f"- `{r['query'][:60]}...` → recall={r['recall_at_k']:.2f} latency={r['latency_ms']:.1f}ms"
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gateway": args.gateway,
        "top_k": args.top_k,
        "mean_recall_at_k": mean_recall,
        "mean_latency_ms": mean_lat,
        "queries_passing": passing,
        "total_queries": len(all_rows),
        "per_query": all_rows,
    }

    print("\n".join(summary_lines))

    out_dir = args.output_dir
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "benchmark-results.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        (out_dir / "benchmark-summary.md").write_text(
            "\n".join(summary_lines) + "\n", encoding="utf-8"
        )
        print(f"\nWrote {out_dir / 'benchmark-results.json'}")
        print(f"Wrote {out_dir / 'benchmark-summary.md'}")

    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(_render_html(payload), encoding="utf-8")
        print(f"Wrote {args.html}")

    rc = 0
    if args.fail_under_mean_recall is not None and mean_recall < args.fail_under_mean_recall:
        print(
            f"\nFAIL: mean recall {mean_recall:.4f} < {args.fail_under_mean_recall}",
            file=sys.stderr,
        )
        rc = 2
    if args.min_queries_passing > 0 and passing < args.min_queries_passing:
        print(
            f"\nFAIL: only {passing} queries passed; need {args.min_queries_passing}",
            file=sys.stderr,
        )
        rc = 2
    return rc


if __name__ == "__main__":
    sys.exit(main())
