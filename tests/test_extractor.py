from training_positions.config import build_config, build_parser
from training_positions.extractor import extract_positions

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


def test_extract_positions_end_to_end(tmp_path):
    input_path = tmp_path / "sample.pgn"
    output_path = tmp_path / "positions.jsonl"
    input_path.write_text(SAMPLE_PGN, encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--opening",
            "Queen's Gambit Declined",
            "--eco",
            "D30:D69",
            "--white-rooks",
            "1:2",
            "--black-rooks",
            "0:2",
            "--phase",
            "endgame",
            "--min-move-number",
            "20",
            "--min-plies-remaining",
            "4",
            "--positions-per-game",
            "1",
            "--max-positions",
            "5",
        ]
    )
    config = build_config(args)
    records = extract_positions(config)
    assert records
    assert records[0]["opening"] == "Queen's Gambit Declined"
    assert records[0]["eco"] == "D35"
    assert "fen" in records[0]
    assert "training_score" in records[0]


def test_summary_mode(tmp_path):
    input_path = tmp_path / "sample.pgn"
    output_path = tmp_path / "summary.jsonl"
    input_path.write_text(SAMPLE_PGN, encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--mode",
            "summary",
            "--opening",
            "Queen's Gambit Declined",
            "--eco",
            "D30:D69",
        ]
    )
    config = build_config(args)
    rows = extract_positions(config)
    assert rows
    assert rows[0]["opening"] == "Queen's Gambit Declined"
