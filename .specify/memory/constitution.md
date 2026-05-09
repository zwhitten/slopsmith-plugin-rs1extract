# RS1 Song Extractor Plugin Constitution

The RS1 Song Extractor (id: `rs1_extract`) splits Rocksmith 1
compatibility multi-song PSARCs into standalone per-song CDLCs that
appear as individual library entries in Slopsmith.

## Core Principles

### I. Non-Destructive
The source `rs1compatibilitydlc_p.psarc` and
`rs1compatibilitydisc_p.psarc` are NEVER modified or deleted.
Extraction reads, builds new per-song PSARCs in
`${dlc_dir}/<title> - <artist>_p.psarc`, then triggers a metadata
rescan. If the user wants to remove the originals, they do it manually.

### II. Skip Existing
Songs already extracted (output filename collision) are silently
skipped — `if (output_dir / out_name).exists(): extracted += 1; continue`
(`routes.py:244-247`). Re-running is safe and idempotent.

### III. Audio Sourcing Splits Disc vs DLC
Disc compatibility songs include their audio inline
(`audio_self_contained = True`, `routes.py:251-253`). DLC compatibility
songs reference WEMs in the parent `songs.psarc` and require
`_find_rs_dir()` to locate the Rocksmith install
(`routes.py:15-33`). Without `songs.psarc`, the DLC pack cannot be
extracted; the disc pack still can.

### IV. Manifest Surgery, Not Conversion
Each extracted song is a faithful slice of the source PSARC: same
SNG, same manifests, same album art, same showlights. The plugin
rewrites only:
- `*_aggregategraph.nt` (built fresh per song)
- The xblock URN paths (`update_xblock`)
- Per-song `.hsan` (from the pack-level HSAN's matching entries)
- The DLC key prefix (`songs_dlc_<key>`)
This guarantees Rocksmith-level fidelity without re-encoding.

### V. WebSocket-Streamed Extraction
Long-running work runs in a thread executor, with progress messages
posted through `progress_queue` (`routes.py:110-171`). The asyncio
loop polls the queue and forwards to the WebSocket; clients receive
per-song stage messages and a final `done` event.

### VI. Idempotent Frontend Hooks
`__slopsmithRs1ExtractHooksInstalled` (`screen.js:8-9`) prevents
re-wrap of `showScreen`. If `showScreen` is missing, the wrapper
installs a no-op (`screen.js:12`).

## Inheritance from Slopsmith Core

Uses `context["get_dlc_dir"]`, `context["extract_meta"]`, and
`context["meta_db"]`. Imports from `psarc`, `rs1_extractor`,
`patcher` — the first lives in core's `lib/`; the latter two live in
this repo. Library rescan is performed by writing to
`_meta_db.put(...)` after each successful extraction.

## Governance

The Wwise BNK / WEM parsing logic is brittle and externally driven —
changes to it must be validated against both packs (DLC + disc) on a
real Rocksmith install. Output filename format
(`{title} - {artist}_p.psarc`) is stable and must not change without
a deprecation step (sloppak converter and other plugins read it).

**Version**: 1.0.0 | **Ratified**: 2026-05-09 | **Last Amended**: 2026-05-09
