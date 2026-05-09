# Clarifications — RS1 Song Extractor

## Q1: Why must `songs.psarc` live next to the DLC folder?
**A**: Disc songs ship audio inside their compatibility pack, but DLC
songs do not — their WEMs live in the Rocksmith install root's
`songs.psarc`. `_find_rs_dir(dlc)` (`routes.py:15-33`) walks up to find
it. Without it, DLC songs are skipped silently for missing audio
(`routes.py:277-278`).

## Q2: Why are `_p.psarc`, `_m.psarc`, and `.disabled.psarc` filtered
when listing extracted songs?
**A**: `routes.py:86-89` excludes the source packs themselves (and
the macOS `_m` variant + the disabled spelling) so the list of
"already extracted" songs reflects only standalone CDLCs that this
plugin or another tool produced.

## Q3: How are filename collisions between two RS1 songs handled?
**A**: `sanitize_filename(info["title"])` + `sanitize_filename(info["artist"])`
form the output name. Two songs with the same sanitized
`{title} - {artist}` would collide; the second hits the `.exists()`
skip and is counted but not extracted. [NEEDS CLARIFICATION: should
we append a suffix on collision instead of skipping?]

## Q4: What happens if `songs.psarc` is found but a specific WEM is missing?
**A**: `routes.py:268-275` tries each candidate WEM; if none yield
data the loop falls through and the song is skipped via
`if not wem_files: continue`. The progress message for the song is
already sent before the skip, so the user sees the song listed but
the final total reflects fewer extractions.

## Q5: Why does the extracted output path use `<title> - <artist>_p.psarc`
and not `<artist> - <title>_p.psarc`?
**A**: Established convention in this repo since v1.0.0. Other
plugins (notably `sloppak_converter` via the meta_db) match on
filename; flipping the order would break library-wide assumptions.
Constitution governance forbids the swap without deprecation.

## Q6: How is the live progress percentage computed?
**A**: `pct = int(5 + (i / max(total, 1)) * 90)` (`routes.py:216`).
The 5–95% band is reserved for songs; the final 5% is for the
post-extraction rescan and `done` message.

## Q7: What if `_extract_meta` raises on a successful new PSARC?
**A**: Wrapped in `try/except: pass` (`routes.py:158-160`). The file
is still on disk; the next library scan picks it up. The user is
not notified.

## Q8: Why no per-song selection UI?
**A**: The pack-level "Extract All" model was the v1.0.0 scope. The
`screen.js` `rs1Extract(pack)` only forwards `dlc | disc | all`;
adding per-song extraction would need a parallel WS handler accepting
song keys. [NEEDS CLARIFICATION: priority of per-song selection.]

## Q9: Are the source RS1 packs disabled after extraction?
**A**: No. They sit alongside the new files. The `.disabled.psarc`
filter (`routes.py:88-89`) suggests a manual workflow some users
follow (rename to `_p.disabled.psarc` to hide the original).
