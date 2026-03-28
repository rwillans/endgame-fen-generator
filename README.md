# Endgame FEN Generator

`endgame-fen-generator` is a pragmatic v1 CLI for extracting realistic chess training positions from large Lichess database dumps. It streams `.pgn`, `.pgn.gz`, and `.pgn.zst` inputs, filters by material/opening/game metadata, optionally uses embedded evals or local Stockfish, and ranks positions for training usefulness instead of dumping every match.

## What v1 does well

- Streams large PGN archives without loading whole files into memory.
- Filters by exact or ranged material constraints for both sides.
- Filters by ECO exact/range plus opening and variation substrings.
- Applies training-oriented heuristics: rated standard games by default, no bullet or ultrabullet, minimum rating 1600, minimum legal moves, minimum plies remaining, and one position per game by default.
- Reads engine evals from PGN comments like `[%eval 0.34]` and `[%eval #-3]`.
- Falls back to local Stockfish only after cheap filters pass.
- Deduplicates by normalized FEN by default and tracks position/family frequency for realism.
- Exports JSONL, CSV, FEN, PGN snippets, or a simple HTML report.
- Supports `summary` and `trainer_export` modes in addition to raw extraction.

## Install

```bash
pip install -r requirements.txt
```

Or:

```bash
pip install -e .
```

## Quick start

```bash
python extract_training_positions.py \
  --input /path/to/lichess_db \
  --white-rooks 1 \
  --white-knights 0 \
  --white-bishops 0 \
  --white-queens 0 \
  --white-pawns 4 \
  --black-rooks 1 \
  --black-knights 0 \
  --black-bishops 0 \
  --black-queens 0 \
  --black-pawns 4 \
  --opening "Queen's Gambit Declined" \
  --eco D30:D69 \
  --min-rating 1600 \
  --time-controls rapid,classical \
  --phase endgame \
  --side-to-move either \
  --min-move-number 20 \
  --eval-min -1.5 \
  --eval-max 1.5 \
  --eval-source pgn_or_stockfish \
  --stockfish-path /path/to/stockfish \
  --stockfish-depth 12 \
  --max-positions 100 \
  --positions-per-game 1 \
  --dedupe normalized_fen \
  --sort-by training_value \
  --output training_positions.jsonl
```

## Input support

- `.pgn`
- `.pgn.gz`
- `.pgn.zst`
- `.torrent` is skipped with a warning because it is not itself a chess database

## CLI notes

Material filters accept exact values or ranges:

- `--white-rooks 1`
- `--black-pawns 3:5`

Opening filters apply to game origin headers:

- `--eco C60`
- `--eco D30:D69`
- `--opening "Sicilian Defense"`
- `--variation "Najdorf"`

Phase modes:

- `exact_material_only`: every position matching the material rules
- `simplified`: total non-pawn material below `--simplified-non-pawn-threshold`
- `endgame`: queens off or total non-pawn material below `--endgame-non-pawn-threshold`
- `final_phase`: only the last `--final-phase-plies` plies

Evaluation modes:

- `none`: never require evals
- `pgn`: use only PGN comments
- `stockfish`: use local Stockfish
- `pgn_or_stockfish`: prefer PGN evals, fall back to Stockfish if configured

Mate handling:

- `exclude`: reject mate scores when eval filtering matters
- `cap`: cap mates to `+/-100` for ranking only
- `include`: treat mates as `+/-100`

Default realism/training settings:

- rated standard games only
- no bullet or ultrabullet
- minimum average rating 1600
- `phase=endgame`
- minimum 2 legal moves
- minimum 4 plies remaining
- dedupe by normalized FEN
- one position per game

## Modes

`extract` writes position records.

`summary` aggregates common opening/family combinations:

```bash
python extract_training_positions.py \
  --input /path/to/db \
  --phase endgame \
  --mode summary \
  --output endgame_summary.jsonl
```

`trainer_export` adds `prompt` and `hidden_answer` fields suitable for a front-end trainer:

```bash
python extract_training_positions.py \
  --input /path/to/db \
  --opening London \
  --training-bias defence \
  --mode trainer_export \
  --output london_defence_pack.jsonl
```

## Config file usage

JSON and YAML are supported:

```bash
python extract_training_positions.py --config examples/balanced_rook_endgames_qgd.yaml
```

CLI flags override config values.

## Output schema

Each extracted record includes rich metadata such as:

- `fen`
- `normalized_fen`
- `opening`, `variation`, `eco`
- `white_elo`, `black_elo`, `average_rating`
- `ply`, `move_number`, `plies_remaining`
- `eval`, `eval_pawns_projected`
- `material_signature`, `family_signature`
- `training_label`, `training_score`
- `next_move_san`, `next_move_uci`
- `position_frequency`, `family_frequency`

Summary mode outputs:

- `opening`
- `family_signature`
- `count`
- `average_rating`
- `sample_fen`
- `sample_label`
- `sample_eval`

## Example use cases

Balanced rook endgames from QGD:

```bash
python extract_training_positions.py \
  --input /db \
  --opening "Queen's Gambit Declined" \
  --eco D30:D69 \
  --white-rooks 1 --white-knights 0 --white-bishops 0 --white-queens 0 --white-pawns 3:5 \
  --black-rooks 1 --black-knights 0 --black-bishops 0 --black-queens 0 --black-pawns 3:5 \
  --eval-source pgn_or_stockfish --stockfish-path /path/to/stockfish \
  --eval-min -1.0 --eval-max 1.0 \
  --output qgd_rook_endgames.jsonl
```

Conversion positions from the Sicilian:

```bash
python extract_training_positions.py \
  --input /db \
  --opening Sicilian \
  --training-bias conversion \
  --eval-source pgn_or_stockfish --stockfish-path /path/to/stockfish \
  --eval-min 0.5 --eval-max 2.0 \
  --output sicilian_conversion.jsonl
```

Defensive positions from the London:

```bash
python extract_training_positions.py \
  --input /db \
  --opening London \
  --training-bias defence \
  --eval-source pgn_or_stockfish --stockfish-path /path/to/stockfish \
  --eval-min -3.0 --eval-max -0.5 \
  --output london_defence.jsonl
```

Opening-to-endgame family summary:

```bash
python extract_training_positions.py \
  --input /db \
  --phase endgame \
  --mode summary \
  --output common_endgame_families.csv \
  --output-format csv
```

## Development

Run tests with:

```bash
pytest
```
