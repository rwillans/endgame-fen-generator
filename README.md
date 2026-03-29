# Endgame FEN Generator

`endgame-fen-generator` is a pragmatic CLI for extracting realistic chess training positions from large Lichess archives. It now treats monthly `.pgn.zst` dumps as the primary workload and is organized as a performance-first pipeline: stream archives, reject games on headers first, replay only plausible late-game stretches, write candidate files, and evaluate with Stockfish only after a position has already survived the cheap filters.

## What it does well

- Streams `.pgn`, `.pgn.gz`, and `.pgn.zst` inputs without unpacking whole archives to disk.
- Separates extraction into explicit stages: archive scan, header filtering, phase-gated replay, candidate writing, optional evaluation, final ranking and export.
- Supports a recommended two-pass workflow so repeated experiments do not require rescanning the raw archive.
- Filters by material, opening, ECO, variation, result, rating, time control, variant, and rated/event metadata.
- Adds lazy engine usage with normalized-FEN caching and optional persistent SQLite eval cache reuse.
- Writes candidate JSONL with enough metadata for downstream scoring and pack building.
- Supports dry-run header summaries, streaming-friendly sampling, shard labels, and candidate/output merging.
- Preserves the existing JSONL/CSV/FEN/PGN/HTML export formats plus `summary` and `trainer_export` modes.

## Install

```bash
pip install -r requirements.txt
```

Or:

```bash
pip install -e .
```

## Recommended large-archive workflow

For very large Lichess dumps, treat raw archive scanning and final pack building as separate steps.

### 1. Quick header-only sanity check

```bash
python extract_training_positions.py \
  --input /data/lichess/ \
  --opening "Queen's Gambit Declined" \
  --eco D30:D69 \
  --min-rating 1600 \
  --time-controls rapid,classical \
  --dry-run-summary \
  --output qgd_header_summary.jsonl
```

This scans files, applies only header filters, and reports counts plus rough opening/ECO/time-control distributions.

### 2. Optional: write a reusable header-pass PGN

```bash
python extract_training_positions.py \
  --input /data/lichess/ \
  --opening "Queen's Gambit Declined" \
  --eco D30:D69 \
  --min-rating 1600 \
  --time-controls classical \
  --write-header-pass-pgn qgd_classical_header_pass.pgn
```

This performs a single full header scan and writes only matching games to a much smaller PGN for repeated downstream experiments.

### 3. First pass: candidate discovery

```bash
python extract_training_positions.py \
  --input /data/lichess/ \
  --opening "Queen's Gambit Declined" \
  --min-rating 1600 \
  --time-controls rapid,classical \
  --phase endgame \
  --only-after-queens-off \
  --start-at-move 20 \
  --stop-after-first-match-per-game \
  --write-candidates qgd_candidates.jsonl
```

This is the fast path for massive archives. It streams the archive, filters on headers first, replays only plausible endgame segments, and writes candidate positions without needing Stockfish.

### 4. Second pass: evaluate and build the pack

```bash
python extract_training_positions.py \
  --read-candidates qgd_candidates.jsonl \
  --eval-min -1.5 \
  --eval-max 1.5 \
  --eval-source stockfish \
  --stockfish-path /path/to/stockfish \
  --stockfish-depth 12 \
  --eval-cache-path eval_cache.sqlite \
  --reuse-eval-cache \
  --output qgd_balanced_training.jsonl
```

This reuses the saved candidates, applies eval filters and training scoring, deduplicates, and exports the final pack.

## Fast workflow shortcut

`--workflow fast_training_pack` applies speed-oriented defaults for large archive work:

- `time_controls=rapid,classical`
- `eval_source=none`
- `positions_per_game=1`
- `stop_after_first_match_per_game=true`
- `max_matches_per_game=1`
- `sample_every_n_plies=2`
- `only_after_queens_off=true`

Example:

```bash
python extract_training_positions.py \
  --input /data/lichess/ \
  --workflow fast_training_pack \
  --opening "Queen's Gambit Declined" \
  --write-candidates qgd_fast_candidates.jsonl
```

## Pipeline stages

- Stage A: archive scan
  Streams supported files and walks folders recursively.
- Stage B: header-only filtering
  Uses headers such as `ECO`, `Opening`, `Variation`, `WhiteElo`, `BlackElo`, `TimeControl`, `Variant`, `Event`, and `Result` before replaying moves.
- Stage C: cheap position search
  Replays only surviving games, respects move/phase gates, and samples plies if requested.
- Stage D: candidate extraction
  Writes positions that pass material, phase, side-to-move, legal-move, and plies-remaining checks.
- Stage E: optional evaluation
  Uses embedded PGN evals or local Stockfish only after candidate extraction.
- Stage F: final ranking and export
  Deduplicates, scores for training value, applies diversity/commonness rules, and writes the pack.

## Candidate files

Candidate files are JSONL and are designed to avoid rescanning raw archives for downstream experiments.

Useful options:

- `--write-candidates path.jsonl`
- `--write-header-pass-pgn filtered_headers.pgn`
- `--read-candidates path.jsonl`
- `--candidate-format jsonl`
- `--append-candidates`
- `--max-candidates N`
- `--merge-candidates path1 path2 ...`
- `--shard-label 2025-01`

Each candidate record includes fields such as:

- `fen`, `normalized_fen`
- `file_path`, `game_key`, `game_index`, `site`
- `ply`, `move_number`, `plies_remaining`
- `last_san_moves`, `next_move_san`, `next_move_uci`
- `opening`, `variation`, `eco`, `result`
- `white_elo`, `black_elo`, `average_rating`, `time_class`, `time_control`
- `white_material`, `black_material`, `material_signature`, `family_signature`
- `embedded_eval`, `eval`, `eval_pawns_projected`
- `shard_label`

## High-value CLI options

### Header filters

- `--eco D30:D69`
- `--opening "Queen's Gambit Declined"`
- `--variation "Exchange Variation"`
- `--result 1/2-1/2`
- `--variant Standard`
- `--event-contains Rated`
- `--min-rating 1600`
- `--time-controls rapid,classical`

### Replay controls

- `--start-at-move N`
- `--sample-every-n-plies N`
- `--only-after-queens-off`
- `--max-non-pawn-material VALUE`
- `--stop-after-first-match-per-game`
- `--max-matches-per-game N`
- `--sample-games N`
- `--sample-candidates N`
- `--random-seed SEED`

### Evaluation controls

- `--eval-source none|pgn|stockfish|pgn_or_stockfish`
- `--eval-min`, `--eval-max`
- `--stockfish-path /path/to/stockfish`
- `--stockfish-depth 12`
- `--stockfish-nodes N`
- `--eval-cache-path eval_cache.sqlite`
- `--reuse-eval-cache`
- `--skip-engine-if-pgn-eval-present`

### Output and merge controls

- `--output pack.jsonl`
- `--output-format jsonl|csv|fen|pgn|html`
- `--merge-outputs path1 path2 ...`

## Additional examples

### Example A: fast first pass over QGD games

```bash
python extract_training_positions.py \
  --input /data/lichess/ \
  --opening "Queen's Gambit Declined" \
  --min-rating 1600 \
  --time-controls rapid,classical \
  --phase endgame \
  --only-after-queens-off \
  --start-at-move 20 \
  --stop-after-first-match-per-game \
  --write-candidates qgd_candidates.jsonl
```

### Example B: evaluate saved candidates

```bash
python extract_training_positions.py \
  --read-candidates qgd_candidates.jsonl \
  --eval-min -1.5 \
  --eval-max 1.5 \
  --eval-source stockfish \
  --stockfish-path /path/to/stockfish \
  --stockfish-depth 12 \
  --output qgd_balanced_training.jsonl
```

### Example C: quick exploratory sample

```bash
python extract_training_positions.py \
  --input /data/lichess/ \
  --eco D30:D69 \
  --sample-games 50000 \
  --phase endgame \
  --write-candidates sample_candidates.jsonl
```

## Modes

`extract` writes detailed position records.

`summary` aggregates common opening or family combinations:

```bash
python extract_training_positions.py \
  --read-candidates qgd_candidates.jsonl \
  --mode summary \
  --output qgd_summary.jsonl
```

`trainer_export` adds `prompt` and `hidden_answer` fields for trainer-style front ends:

```bash
python extract_training_positions.py \
  --read-candidates qgd_candidates.jsonl \
  --mode trainer_export \
  --output qgd_trainer.jsonl
```

## Config files

JSON and YAML are supported:

```bash
python extract_training_positions.py --config examples/balanced_rook_endgames_qgd.yaml
```

CLI flags override config values.

## Development

Run tests with:

```bash
pytest
```

