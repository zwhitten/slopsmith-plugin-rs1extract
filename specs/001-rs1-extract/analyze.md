# Analyze — RS1 Song Extractor

## Coverage

| Area | Code | Tests | Spec |
|------|------|-------|------|
| RS dir resolution | `routes.py:15-33` | None | FR-2 |
| Status manifest scan | `routes.py:42-95` | None | US-1, FR-1, FR-3 |
| Audio sourcing | `routes.py:204-211, 251-275` | None | FR-8, FR-9 |
| Per-song surgery | `routes.py:280-345` | None | FR-4..7 |
| Library rescan | `routes.py:151-160` | None | US-4 |
| Frontend WS client | `screen.js:99-137` | None | US-2 |

No automated tests, no fixture PSARCs, no CI workflow.

## Drift

1. **Output filename convention is implicit**: documented in
   constitution §VI by reference, but not codified anywhere a
   downstream plugin can read. Sloppak converter & meta_db rely on it.
2. **Sanitization rules** live in `rs1_extractor.sanitize_filename`
   which this spec does not document. A change there silently changes
   output filenames.
3. **README** mentions `Docker Setup` env var `DLC_DIR=/rocksmith/dlc`
   which is core-side, not handled by this plugin directly.
4. **CLAUDE.md is the speckit stub**.
5. **Progress percentage curve** (5–95%) is hard-coded; the
   post-extraction rescan window (95–100%) is invisible to users
   because no progress messages fire during it.

## Gaps

- No tests against fixture PSARCs (`rs1compatibilitydlc_p.psarc`,
  `rs1compatibilitydisc_p.psarc`) — small synthetic ones could verify
  end-to-end flow without bundling the real files.
- No coverage of edge cases:
  - Songs whose BNK has no media id.
  - Songs with multiple WEMs (only the first is taken).
  - Filename sanitization producing identical names for two songs.
- Failures during extraction are logged via `traceback.print_exc()`
  but only one error is surfaced to the WS client (the last).
- The DLC pack scan reads every JSON in the pack on every status
  fetch — could cache.

## Recommendations

1. **Add a smoke test**: a small fixture PSARC with two synthetic
   songs to exercise the full pipeline (BNK parse → WEM lookup →
   manifest surgery → output PSARC).
2. **Codify the output filename**: expose
   `rs1_extractor.compose_output_name(title, artist)` and document it
   in this spec so downstream code can match on it deterministically.
3. **Cache `/status` results**: small TTL (30s) keyed on the source
   PSARC mtimes — avoids re-parsing on every page mount.
4. **Append `_2`, `_3` on collision** instead of skipping the second
   song with the same sanitized name (clarify Q3).
5. **Surface skipped songs** with reason codes
   (`already_extracted`, `no_audio`, `no_manifest`) in the final
   summary message.
6. **Replace CLAUDE.md** with a one-pager summarizing the
   manifest-surgery rules.

## Risk assessment

- **Medium**: the parsing surface is brittle and depends on Rocksmith
  format details that are not formally documented anywhere. A future
  Rocksmith patch could in theory break it (but Rocksmith 2014 is no
  longer updated, so this risk is largely historical).
- **Low** for runtime safety: temp dirs auto-clean, source files
  untouched, library rescan gracefully retries.
