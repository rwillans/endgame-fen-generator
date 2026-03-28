import chess

from training_positions.config import parse_range_constraint
from training_positions.filters import dedupe_key, eco_matches, family_signature, material_signature, normalized_fen


def test_parse_range_constraint_exact_and_range():
    exact = parse_range_constraint("3")
    ranged = parse_range_constraint("2:5")
    assert exact.minimum == 3 and exact.maximum == 3
    assert ranged.minimum == 2 and ranged.maximum == 5


def test_eco_matches_exact_and_range():
    assert eco_matches("D35", ("D30:D69",))
    assert eco_matches("C60", ("C60",))
    assert not eco_matches("B12", ("D30:D69",))


def test_normalized_and_family_signatures():
    board = chess.Board("8/8/8/8/8/8/3k4/3K4 w - - 0 1")
    assert normalized_fen(board) == "8/8/8/8/8/8/3k4/3K4 w - -"
    assert material_signature(board).startswith("W:q0r0b0k0p0|B:q0r0b0k0p0")
    assert family_signature(board).startswith("W:q0r0b0k0p0|B:q0r0b0k0p0|P:")
    assert dedupe_key(board, "normalized_fen") == "8/8/8/8/8/8/3k4/3K4 w - -"
