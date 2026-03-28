from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any

from .filters import flatten_record


def trainer_payload(record: dict[str, Any]) -> dict[str, Any]:
    next_move = record.get("next_move_san") or record.get("next_move_uci")
    enriched = dict(record)
    enriched["prompt"] = "Find the move" if next_move else "Choose a plan"
    enriched["hidden_answer"] = next_move
    enriched["trainer_label"] = record.get("training_label")
    return enriched


def _fen_for_record(record: dict[str, Any]) -> str:
    return str(record.get("fen") or record.get("sample_fen") or "")


def write_records(records: list[dict[str, Any]], output_path: Path, output_format: str, mode: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [trainer_payload(record) for record in records] if mode == "trainer_export" else records

    if output_format == "jsonl":
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            for record in payload:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        return

    if output_format == "csv":
        flattened = [flatten_record(dict(record)) for record in payload]
        fieldnames: list[str] = []
        for record in flattened:
            for key in record.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flattened)
        return

    if output_format == "fen":
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            for record in payload:
                handle.write(_fen_for_record(record) + "\n")
        return

    if output_format == "pgn":
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            for record in payload:
                fen = _fen_for_record(record)
                headers = [
                    '[Event "Training Position"]',
                    '[Site "Generated"]',
                    f'[FEN "{fen}"]',
                    '[SetUp "1"]',
                    '[Result "*"]',
                ]
                comment = json.dumps(
                    {
                        "label": record.get("training_label") or record.get("sample_label"),
                        "score": record.get("training_score") or record.get("count"),
                        "next_move": record.get("next_move_san") or record.get("next_move_uci"),
                    },
                    ensure_ascii=True,
                )
                handle.write("\n".join(headers))
                handle.write(f"\n\n{{{comment}}} *\n\n")
        return

    if output_format == "html":
        rows = []
        for record in payload:
            rows.append(
                "<tr>"
                f"<td>{html.escape(str(record.get('opening') or record.get('eco') or 'Unknown'))}</td>"
                f"<td>{html.escape(_fen_for_record(record))}</td>"
                f"<td>{html.escape(str(record.get('training_label') or record.get('sample_label') or ''))}</td>"
                f"<td>{html.escape(str(record.get('eval_pawns_projected') or record.get('sample_eval') or ''))}</td>"
                f"<td>{html.escape(str(record.get('training_score') or record.get('count') or ''))}</td>"
                "</tr>"
            )
        document = (
            "<!doctype html><html><head><meta charset='utf-8'><title>Training Positions</title>"
            "<style>body{font-family:Georgia,serif;margin:2rem;background:#f6f2ea;color:#1f1f1f}"
            "table{border-collapse:collapse;width:100%}th,td{border:1px solid #c6b9a3;padding:.6rem;vertical-align:top}"
            "th{background:#e4d8c5;text-align:left}code{font-size:.92rem}</style></head><body>"
            "<h1>Training Positions</h1><table><thead><tr><th>Opening</th><th>FEN</th><th>Label</th><th>Eval</th><th>Score</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></body></html>"
        )
        output_path.write_text(document, encoding="utf-8")
        return

    raise ValueError(f"Unsupported output format: {output_format}")
