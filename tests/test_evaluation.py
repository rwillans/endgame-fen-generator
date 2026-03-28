import chess

from training_positions.config import build_config, build_parser
from training_positions.evaluation import extract_eval_from_comment, parse_eval_token, project_eval



def build_test_config(*extra):
    parser = build_parser()
    args = parser.parse_args(["--input", "in.pgn", "--output", "out.jsonl", *extra])
    return build_config(args)


def test_extract_eval_from_comment_cp():
    eval_info = extract_eval_from_comment("{ [%eval 0.34] }")
    assert eval_info is not None
    assert eval_info.pawns == 0.34
    assert eval_info.cp == 34


def test_extract_eval_from_comment_mate():
    eval_info = extract_eval_from_comment("{ [%eval #-3] }")
    assert eval_info is not None
    assert eval_info.mate == -3


def test_project_eval_side_to_move():
    board = chess.Board()
    eval_info = parse_eval_token("0.90", "pgn")
    config = build_test_config("--eval-perspective", "side_to_move")
    assert project_eval(eval_info, board, config, for_filter=True) == 0.9
    board.push_san("e4")
    assert project_eval(eval_info, board, config, for_filter=True) == -0.9


def test_project_eval_cap_policy_rejects_for_filter():
    board = chess.Board()
    eval_info = parse_eval_token("#3", "pgn")
    config = build_test_config("--mate-score-policy", "cap")
    assert project_eval(eval_info, board, config, for_filter=True) is None
    assert project_eval(eval_info, board, config, for_filter=False) == 100.0
