# Implementation Plan — RS1 Song Extractor

## Architecture

```
slopsmith-plugin-rs1extract/
├── plugin.json
├── routes.py          — FastAPI status + WebSocket extract
├── rs1_extractor.py   — pure-Python per-song extraction primitives
├── screen.html        — pack list + progress UI
├── screen.js          — status loader + WS client
└── README.md
```

Heavy lifting is split between `routes.py` (orchestration, progress)
and the helper module `rs1_extractor.py` (PSARC parsing, manifest
surgery, WEM matching). `routes.py` also imports `pack_psarc` from
core's `patcher` module (`routes.py:186-187`).

## Backend (`routes.py`, 364 lines)

### Helpers
- `_find_rs_dir(dlc_dir)` (15-33) — `/rocksmith` → parent →
  Steam fallbacks.

### Endpoints
- `GET /api/plugins/rs1_extract/status` (43-95) — pack manifest scan
  + audio sourcing detection.
- `WS  /ws/plugins/rs1_extract/extract?pack={dlc|disc|all}` (97-363).

### `_do_extract` closure (112-172)
1. Open `songs.psarc` once if found.
2. For each pack (DLC, disc), call `_extract_with_progress`.
3. After all packs complete, walk DLC dir and put new metadata via
   `_extract_meta` + `_meta_db.put`.
4. Send `{done: true, total}`.

### `_extract_with_progress` closure (173-345)
For one pack:
1. List xblocks → derive `song_keys`.
2. Read pack-level flat models, HSAN.
3. If audio external, pre-fetch BNKs from `songs.psarc`.
4. For each song key:
   a. Read manifests, SNGs, album art, showlights, xblock.
   b. Pick info from non-vocals manifest.
   c. Skip-if-exists.
   d. Resolve audio: BNK in pack (disc) or pre-fetched (DLC).
   e. Parse Wwise BNK media id → fetch `<id>.wem`.
   f. Build temp dir tree:
      `appid.appid`, `audio/windows/`, `flatmodels/rs/`,
      `gamexblocks/nsongs/`, `gfxassets/album_art/`,
      `manifests/<dlc_key>/`, `songs/arr/`, `songs/bin/generic/`,
      `<key>_aggregategraph.nt`.
   g. `pack_psarc(tmpdir, output_dir / out_name)`.

### Concurrency model
- The full closure runs in `loop.run_in_executor(None, _do_extract)`
  (line 347).
- Progress messages enqueue via `progress_queue.put_nowait(...)`.
- The websocket coroutine drains with `await asyncio.wait_for(...,
  timeout=2.0)`; on timeout it checks `task.done()` and exits if so
  (lines 350-360).

## Frontend (`screen.html` + `screen.js`)

### `screen.html` (17 lines)
- `#rs1-status` — env / packs detected.
- `#rs1-packs` — pack cards with song lists + Extract buttons.
- `#rs1-progress` — progress bar + stage label.
- `#rs1-result` — success/failure card with Back.

### `screen.js` (137 lines)
- Idempotency guard `__slopsmithRs1ExtractHooksInstalled`
  (lines 8-18).
- `rs1LoadStatus()` (20-97) — fetches status, renders pack cards.
- `rs1Extract(pack)` (99-137) — opens WS, updates progress bar +
  stage, swaps to result card on done/error.

## Inputs from core (context dict)

- `get_dlc_dir() -> Path`
- `extract_meta(psarc_path) -> dict`
- `meta_db` with `.get(filename, mtime, size)` and
  `.put(filename, mtime, size, meta)`

## Risks

| Risk | Mitigation |
|------|-----------|
| Wwise BNK format change | Externally fixed; failure is silent skip |
| Filename collision between songs | Skipped (clarify Q3) |
| Long extraction blocks UI | Run in executor with WS progress |
| `songs.psarc` not found on Linux/Steam Proton | Multiple fallback paths |
| `_extract_meta` failure | try/except; next library scan retries |

## Open items

- Per-song selection UI [NEEDS CLARIFICATION].
- Force re-extract / delete originals [NEEDS CLARIFICATION].
- Better error reporting per skipped song.
