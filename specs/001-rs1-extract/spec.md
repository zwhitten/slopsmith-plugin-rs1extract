# Feature Specification: RS1 Song Extractor

**Plugin id**: `rs1_extract` (`plugin.json:2`)
**Nav**: "RS1 Import" (`plugin.json:6`)
**Status**: Shipped (v1.0.0)

## Summary

Splits Rocksmith 2014's RS1 compatibility packs (each containing 100+
songs in a single PSARC) into individual playable per-song CDLCs that
Slopsmith treats as normal library entries.

## User Stories

### US-1 — Discover RS1 packs and audio source
**As** a Rocksmith owner with the RS1 compat packs installed
**I want** the plugin to detect what's available
**So that** I know whether DLC, Disc, or both can be extracted.

- **Given** the user opens the RS1 Import screen
- **When** `rs1LoadStatus()` runs (`screen.js:20`)
- **Then** `GET /api/plugins/rs1_extract/status` returns `{packs[],
  has_songs_psarc, rs_dir}` (`routes.py:42-95`).
- **And** packs are detected by filename:
  `rs1compatibilitydlc_p.psarc`, `rs1compatibilitydisc_p.psarc`.
- **And** each pack lists its songs via manifest scan, deduplicated by
  SongKey, excluding `Vocals`/`ShowLights`/`JVocals` arrangements
  (`routes.py:71-75`).

### US-2 — Extract one pack or all packs
**As** the same user
**I want** to click "Extract All" on a pack or "Extract All Packs" on
both
**So that** the songs appear individually in my library.

- **Given** at least one pack is detected
- **When** the user clicks Extract
- **Then** `WS /ws/plugins/rs1_extract/extract?pack={dlc|disc|all}`
  opens (`screen.js:106`).
- **And** the server runs `_extract_with_progress` per pack in a
  thread executor (`routes.py:97-345`).
- **And** progress messages stream:
  `{stage: "Processing RS1 ... pack...", progress: 5}` then per-song
  `{stage: "[i/n] Artist - Title", progress: pct}` then
  `{done: true, progress: 100, total}`.

### US-3 — Skip already-extracted songs
**As** a returning user re-running the extractor
**I want** previously extracted songs to be skipped instantly
**So that** I don't wait through a full re-run.

- **Given** `${dlc_dir}/<title> - <artist>_p.psarc` exists for some songs
- **When** the extractor reaches each song
- **Then** the existence check (`routes.py:244-247`) skips it,
  counting it as extracted.

### US-4 — Library auto-rescan on completion
**As** the same user
**I want** the new songs to show up in the library automatically
**So that** I don't trigger a manual scan.

- **When** all packs finish
- **Then** the plugin walks `${dlc_dir}` for `*_p.psarc` files,
  diffs against `_meta_db`, and inserts metadata for new files
  (`routes.py:151-160`).

## Functional Requirements

- **FR-1** Detect packs by exact filename in DLC dir.
- **FR-2** `_find_rs_dir(dlc_dir)` resolves the Rocksmith install:
  `/rocksmith` → `dlc.parent.name == "Rocksmith2014"` → common Steam
  paths (`routes.py:15-33`).
- **FR-3** `has_songs_psarc` is true iff `<rs_dir>/songs.psarc` exists.
- **FR-4** Per-song output filename: `{sanitized_title} -
  {sanitized_artist}_p.psarc` (`routes.py:240-241`).
- **FR-5** xblock URN rewrite via
  `update_xblock(xblock_data, manifest_dir, dlc_key)` where
  `dlc_key = f"songs_dlc_{key}"`.
- **FR-6** Per-song HSAN built from matching entries in pack HSAN via
  `build_hsan` (`routes.py:319-321`).
- **FR-7** Aggregate graph built per song via `build_aggregate_graph`
  (`routes.py:337-339`).
- **FR-8** Audio: disc pack reads BNK + WEM from itself; DLC pack
  reads from `<rs_dir>/songs.psarc`.
- **FR-9** Wwise BNK media-id parsed by `parse_bnk_wem_id` to locate
  the matching `.wem` (`routes.py:261-264`).
- **FR-10** Manifests excluded: `_vocals` is the preferred filter for
  `info` extraction (`routes.py:226-232`); other arrangements are
  preserved verbatim.
- **FR-11** Skip songs that have no matching WEM (`routes.py:277-278`).
- **FR-12** Library rescan after extraction batch
  (`routes.py:151-160`).

## Non-Functional Requirements

- **NFR-1** Extraction runs in a thread executor; the asyncio loop
  stays responsive (`routes.py:347`).
- **NFR-2** Progress queue is bounded by message production rate, not
  size — clients drain or fall behind (acceptable for one slow viewer).
- **NFR-3** Per-song temp directory is removed after packing
  (`with tempfile.TemporaryDirectory(): ...`).

## Out of Scope

- Per-song selective extraction [NEEDS CLARIFICATION: the screen
  shows the song list but offers no per-song checkbox; users extract
  whole packs].
- Re-encoding audio (WEMs are copied as-is; tuning / pitch shift not
  applied).
- Updating already-extracted songs when the source pack updates
  [NEEDS CLARIFICATION: should we offer a "force re-extract" button?].
- Disabling the original RS1 pack files automatically.

## Key Entities

- **Pack**: `(name, filename, song_count, songs[])` discovered from
  manifest scan.
- **Song**: `(key, title, artist, arrangements[])` keyed by
  `Attributes.SongKey`.
- **DLC key**: `songs_dlc_<key>` — the per-song manifest directory
  name in the output PSARC.
