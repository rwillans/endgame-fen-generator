from __future__ import annotations

import json

from training_positions.candidate_reader import iter_candidates_from_paths
from training_positions.candidate_writer import CandidateWriter
from training_positions.config import build_config, build_parser
from training_positions.eval_cache import EvalCache
from training_positions.extractor import extract_positions
from training_positions.models import CandidatePosition, EvalInfo

SAMPLE_PGN = """[Event \"Rated Rapid game\"]
[Site \"https://lichess.org/example\"]
[White \"Alice\"]
[Black \"Bob\"]
[Result \"1/2-1/2\"]
[WhiteElo \"2100\"]
[BlackElo \"2050\"]
[TimeControl \"600+5\"]
[ECO \"D35\"]
[Opening \"Queen's Gambit Declined\"]
[Variation \"Exchange Variation\"]
[SetUp \"1\"]
[FEN \"8/6kp/3r2p1/3P4/1p3P2/1P4P1/P5KP/3R4 w - - 0 20\"]

20. Kf3 Kf7 21. Ke4 Ke7 22. Rc1 Kd7 23. Rc2 h6 24. h4 h5 1/2-1/2
"""

HEADER_FILTER_PGN = """[Event \"Rated Rapid game\"]
[Site \"https://lichess.org/skipme\"]
[White \"Skip\"]
[Black \"Skip\"]
[Result \"1-0\"]
[WhiteElo \"2100\"]
[BlackElo \"2050\"]
[TimeControl \"600+5\"]
[ECO \"C20\"]
[Opening \"King's Pawn Game\"]

1. TotallyIllegalMove 1-0

""" + SAMPLE_PGN

QUEENS_OFF_PGN = """[Event \"Rated Rapid game\"]
[Site \"https://lichess.org/queensoff\"]
[White \"Alice\"]
[Black \"Bob\"]
[Result \"1/2-1/2\"]
[WhiteElo \"2000\"]
[BlackElo \"2000\"]
[TimeControl \"600+5\"]
[ECO \"A00\"]
[Opening \"Queen Trade Test\"]
[SetUp \"1\"]
[FEN \"3qk3/8/8/8/8/8/4P3/3QK3 w - - 0 1\"]

1. Qxd8+ Kxd8 2. e4 Ke7 3. Ke2 Ke6 1/2-1/2
"""


def build_test_config(*extra):
    parser = build_parser()
    args = parser.parse_args(list(extra))
    return build_config(args)


def make_candidate() -> CandidatePosition:
    return CandidatePosition(
        game_key="https://lichess.org/example",
        file_path="sample.pgn",
        game_index=1,
        event="Rated Rapid game",
        site="https://lichess.org/example",
        white="Alice",
        black="Bob",
        white_elo=2100,
        black_elo=2050,
        average_rating=2075.0,
        rated=True,
        time_class="rapid",
        time_control="600+5",
        variant="Standard",
        eco="D35",
        opening="Queen's Gambit Declined",
        variation="Exchange Variation",
        result="1/2-1/2",
        ply=40,
        move_number=20,
        plies_remaining=6,
        side_to_move="white",
        legal_moves=10,
        fen="8/6kp/3r2p1/3P4/1p3P2/1P4P1/P5KP/3R4 w - - 0 20",
        normalized_fen="8/6kp/3r2p1/3P4/1p3P2/1P4P1/P5KP/3R4 w - -",
        piece_placement="8/6kp/3r2p1/3P4/1p3P2/1P4P1/P5KP/3R4",
        piece_placement_plus_turn="8/6kp/3r2p1/3P4/1p3P2/1P4P1/P5KP/3R4 w",
        material_signature="W:q0r1b0k0p4|B:q0r1b0k0p4",
        family_signature="W:q0r1b0k0p4|B:q0r1b0k0p4|P:0,1,0,1,0,1,0,1|P:0,1,0,1,0,1,0,1",
        dedupe_key="8/6kp/3r2p1/3P4/1p3P2/1P4P1/P5KP/3R4 w - -",
        next_move_uci="e2e4",
        next_move_san="Ke4",
        last_san_moves=["Kf3", "Kf7"],
        white_material={"queens": 0, "rooks": 1, "bishops": 0, "knights": 0, "pawns": 4},
        black_material={"queens": 0, "rooks": 1, "bishops": 0, "knights": 0, "pawns": 4},
        embedded_eval=EvalInfo(source="pgn", raw="0.42", pawns=0.42, cp=42),
        shard_label="2025-01",
    )


def test_header_only_filter_skips_move_replay_for_rejected_games(tmp_path):
    input_path = tmp_path / "header_filter.pgn"
    output_path = tmp_path / "positions.jsonl"
    input_path.write_text(HEADER_FILTER_PGN, encoding="utf-8")

    config = build_test_config(
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--opening",
        "Queen's Gambit Declined",
        "--eco",
        "D30:D69",
        "--start-at-move",
        "20",
    )
    records = extract_positions(config)
    assert records
    assert all(record["site"] != "https://lichess.org/skipme" for record in records)


def test_two_pass_candidate_workflow(tmp_path):
    input_path = tmp_path / "sample.pgn"
    candidate_path = tmp_path / "candidates.jsonl"
    output_path = tmp_path / "positions.jsonl"
    input_path.write_text(SAMPLE_PGN, encoding="utf-8")

    pass1 = build_test_config(
        "--input",
        str(input_path),
        "--opening",
        "Queen's Gambit Declined",
        "--write-candidates",
        str(candidate_path),
        "--start-at-move",
        "20",
    )
    records = extract_positions(pass1)
    assert records == []
    assert candidate_path.exists()
    assert candidate_path.read_text(encoding="utf-8").strip()

    pass2 = build_test_config(
        "--read-candidates",
        str(candidate_path),
        "--output",
        str(output_path),
    )
    second_pass_records = extract_positions(pass2)
    assert second_pass_records
    assert second_pass_records[0]["opening"] == "Queen's Gambit Declined"


def test_candidate_file_roundtrip(tmp_path):
    candidate_path = tmp_path / "roundtrip.jsonl"
    candidate = make_candidate()

    with CandidateWriter(candidate_path) as writer:
        assert writer.write(candidate)

    loaded = list(iter_candidates_from_paths((candidate_path,)))
    assert len(loaded) == 1
    assert loaded[0].fen == candidate.fen
    assert loaded[0].embedded_eval is not None
    assert loaded[0].embedded_eval.pawns == 0.42
    assert loaded[0].last_san_moves == ["Kf3", "Kf7"]


def test_stop_after_first_match_per_game_limits_candidate_discovery(tmp_path):
    input_path = tmp_path / "sample.pgn"
    all_candidates_path = tmp_path / "all_candidates.jsonl"
    first_only_path = tmp_path / "first_only.jsonl"
    input_path.write_text(SAMPLE_PGN, encoding="utf-8")

    config_all = build_test_config(
        "--input",
        str(input_path),
        "--opening",
        "Queen's Gambit Declined",
        "--write-candidates",
        str(all_candidates_path),
        "--start-at-move",
        "20",
    )
    extract_positions(config_all)

    config_first = build_test_config(
        "--input",
        str(input_path),
        "--opening",
        "Queen's Gambit Declined",
        "--write-candidates",
        str(first_only_path),
        "--start-at-move",
        "20",
        "--stop-after-first-match-per-game",
    )
    extract_positions(config_first)

    all_lines = [line for line in all_candidates_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    first_lines = [line for line in first_only_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(all_lines) > 1
    assert len(first_lines) == 1


def test_sample_candidates_mode_reads_subset(tmp_path):
    candidate_path = tmp_path / "sample_candidates.jsonl"
    output_path = tmp_path / "sampled.jsonl"
    candidates = [make_candidate(), make_candidate(), make_candidate()]
    candidates[1].game_key = "https://lichess.org/example2"
    candidates[1].site = "https://lichess.org/example2"
    candidates[2].game_key = "https://lichess.org/example3"
    candidates[2].site = "https://lichess.org/example3"

    with CandidateWriter(candidate_path) as writer:
        for candidate in candidates:
            writer.write(candidate)

    config = build_test_config(
        "--read-candidates",
        str(candidate_path),
        "--output",
        str(output_path),
        "--sample-candidates",
        "1",
        "--random-seed",
        "7",
    )
    records = extract_positions(config)
    assert len(records) == 1


def test_eval_cache_reuse_supplies_evaluation_without_engine(tmp_path):
    candidate_path = tmp_path / "cached_candidates.jsonl"
    output_path = tmp_path / "cached_output.jsonl"
    cache_path = tmp_path / "eval_cache.sqlite"
    candidate = make_candidate()

    with CandidateWriter(candidate_path) as writer:
        writer.write(candidate)

    with EvalCache(cache_path, reuse=True) as cache:
        cache.put(candidate.normalized_fen, EvalInfo(source="stockfish", raw="0.42", pawns=0.42, cp=42))

    config = build_test_config(
        "--read-candidates",
        str(candidate_path),
        "--output",
        str(output_path),
        "--eval-source",
        "stockfish",
        "--eval-cache-path",
        str(cache_path),
        "--reuse-eval-cache",
    )
    records = extract_positions(config)
    assert records[0]["eval"]["source"] == "stockfish"
    assert records[0]["eval_pawns_projected"] == 0.42


def test_phase_gated_scanning_waits_until_queens_are_off(tmp_path):
    input_path = tmp_path / "queens_off.pgn"
    candidate_path = tmp_path / "queens_off_candidates.jsonl"
    input_path.write_text(QUEENS_OFF_PGN, encoding="utf-8")

    config = build_test_config(
        "--input",
        str(input_path),
        "--opening",
        "Queen Trade Test",
        "--write-candidates",
        str(candidate_path),
        "--start-at-move",
        "1",
        "--only-after-queens-off",
        "--min-plies-remaining",
        "1",
        "--min-legal-moves",
        "1",
    )
    extract_positions(config)

    payloads = [json.loads(line) for line in candidate_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert payloads
    assert all("q" not in payload["fen"].lower() for payload in payloads)
    assert min(payload["ply"] for payload in payloads) >= 2




def test_write_header_pass_pgn_streams_only_matching_games(tmp_path):
    input_path = tmp_path / "header_filter.pgn"
    header_pass_path = tmp_path / "header_pass_only.pgn"
    input_path.write_text(HEADER_FILTER_PGN, encoding="utf-8")

    config = build_test_config(
        "--input",
        str(input_path),
        "--opening",
        "Queen's Gambit Declined",
        "--eco",
        "D30:D69",
        "--write-header-pass-pgn",
        str(header_pass_path),
    )
    records = extract_positions(config)
    assert records == []
    written = header_pass_path.read_text(encoding="utf-8")
    assert "Queen's Gambit Declined" in written
    assert "King's Pawn Game" not in written
    assert written.count('[Site ') == 1
