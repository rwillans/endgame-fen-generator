from training_positions.config import build_config, build_parser
from training_positions.extractor import extract_positions

SAMPLE_PGN = """[Event \"Rated Rapid game\"]
[Site \"https://lichess.org/example\"]
[White \"Alice\"]
[Black \"Bob\"]
[Result \"0-1\"]
[WhiteElo \"2100\"]
[BlackElo \"2050\"]
[TimeControl \"600+5\"]
[ECO \"D35\"]
[Opening \"Queen's Gambit Declined\"]
[Variation \"Exchange Variation\"]

1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. cxd5 exd5 5. Bg5 c6 6. e3 Be7 7. Bd3 O-O
8. Qc2 Nbd7 9. Nge2 Re8 10. O-O Nf8 11. f3 Ng6 12. Rad1 Be6 13. e4 dxe4
14. fxe4 Ng4 15. Bxe7 Qxe7 16. Qd2 Rad8 17. h3 Nf6 18. Qe3 c5 19. d5 Bxd5
20. Rxf6 gxf6 21. Nxd5 Rxd5 22. exd5 Qxe3+ 23. Kh2 Ne5 24. Bb5 Rd8 25. Nc3 a6
26. Bf1 b5 27. d6 Qf4+ 28. Kg1 Qe3+ 29. Kh2 b4 30. Nd5 Nf3+ 31. gxf3 Qf2+
32. Bg2 Rxd6 33. Ne7+ Kf8 34. Rxd6 Kxe7 35. Rxa6 Qxb2 36. Kg3 c4 37. Ra7+
Kf8 38. f4 c3 39. Bd5 c2 40. Rxf7+ Ke8 41. Rxh7 c1=Q 42. Bf7+ Kd8 43. Bb3
Qc3+ 44. Kg4 Qg2+ 45. Kf5 Qdd3+ 46. Kxf6 Qgg6+ 47. Ke5 Qdd6# 0-1
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
