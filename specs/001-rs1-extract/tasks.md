# Tasks — RS1 Song Extractor

## US-1: Status detection

- [x] **DONE** `_find_rs_dir` covers `/rocksmith`, parent name match,
  Steam fallbacks (`routes.py:15-33`).
- [x] **DONE** `GET /status` enumerates DLC + Disc packs and lists
  songs (`routes.py:42-95`).
- [x] **DONE** Filter Vocals/ShowLights/JVocals (`routes.py:71-72`).
- [x] **DONE** `has_songs_psarc` flag surfaced.
- [x] **DONE** Frontend renders the pack cards with song lists
  (`screen.js:55-85`).
- [ ] **OPEN [P]** Per-pack mtime / size displayed for cache-bust UX.

## US-2: Extraction

- [x] **DONE** WebSocket `extract?pack={dlc|disc|all}`.
- [x] **DONE** `pack=all` orchestrates both packs.
- [x] **DONE** Per-song progress messages with title/artist.
- [x] **DONE** Disc songs: self-contained audio (`audio_self_contained=True`).
- [x] **DONE** DLC songs: audio fetched from `songs.psarc` once
  (pre-cached in `audio_bnks`).
- [x] **DONE** Wwise BNK → WEM resolution (`parse_bnk_wem_id`).
- [x] **DONE** xblock URN rewrite (`update_xblock`).
- [x] **DONE** Per-song HSAN + aggregate graph built.
- [x] **DONE** Pack output via `pack_psarc`.
- [ ] **OPEN** Per-song extraction (clarify Q8).
- [ ] **OPEN [P]** Force re-extract option for already-extracted songs.

## US-3: Idempotent re-runs

- [x] **DONE** `(output_dir / out_name).exists()` skip
  (`routes.py:244-247`).
- [ ] **OPEN [P]** Track previously-skipped vs newly-extracted in
  the final summary message.

## US-4: Library rescan

- [x] **DONE** `_meta_db.get` lookup + `_meta_db.put` insert
  (`routes.py:151-160`).
- [ ] **OPEN [P]** Emit a `{stage: "rescanning", ...}` progress
  message during this phase (currently silent until `done`).

## Frontend

- [x] **DONE** Idempotent `showScreen` wrap.
- [x] **DONE** Status / packs / progress / result section toggling.
- [x] **DONE** Error path renders red card with Back button.
- [ ] **OPEN [P]** Add a copy-to-clipboard button for the failure
  message to ease bug reporting.

## Concurrency / streaming

- [x] **DONE** `loop.run_in_executor` keeps loop responsive.
- [x] **DONE** `progress_queue` drained with timeout.
- [ ] **OPEN [P]** Add a heartbeat message every N seconds to detect
  hung jobs.

## Spec-kit hygiene

- [x] **DONE** Constitution.
- [x] **DONE** Spec / clarify / plan / tasks / analyze.
