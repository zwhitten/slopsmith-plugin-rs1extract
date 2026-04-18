"""RS1 Song Extractor plugin — split RS1 compatibility packs into individual CDLCs."""

import asyncio
import json
import os
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect

_get_dlc_dir = None
_extract_meta = None
_meta_db = None


def _find_rs_dir(dlc_dir):
    """Find the Rocksmith install directory from the DLC path."""
    # Check Docker mount first
    if Path("/rocksmith/songs.psarc").exists():
        return Path("/rocksmith")
    # DLC is usually at .../Rocksmith2014/dlc
    if dlc_dir and dlc_dir.parent.name == "Rocksmith2014":
        return dlc_dir.parent
    # Try common locations
    common = [
        Path.home() / ".local/share/Steam/steamapps/common/Rocksmith2014",
        Path.home() / ".steam/steam/steamapps/common/Rocksmith2014",
        Path("C:/Program Files (x86)/Steam/steamapps/common/Rocksmith2014"),
        Path("C:/Program Files/Steam/steamapps/common/Rocksmith2014"),
    ]
    for p in common:
        if p.exists():
            return p
    return None


def setup(app, context):
    global _get_dlc_dir, _extract_meta, _meta_db
    _get_dlc_dir = context["get_dlc_dir"]
    _extract_meta = context["extract_meta"]
    _meta_db = context["meta_db"]

    @app.get("/api/plugins/rs1_extract/status")
    def rs1_status():
        """Check which RS1 packs are available and what's already extracted."""
        dlc = _get_dlc_dir()
        if not dlc:
            return {"error": "DLC folder not configured"}

        rs_dir = _find_rs_dir(dlc)
        has_songs_psarc = rs_dir and (rs_dir / "songs.psarc").exists()

        packs = []
        for name, filename in [("DLC", "rs1compatibilitydlc_p.psarc"),
                                ("Disc", "rs1compatibilitydisc_p.psarc")]:
            psarc = dlc / filename
            if psarc.exists():
                # Count songs inside
                try:
                    from psarc import read_psarc_entries
                    files = read_psarc_entries(str(psarc), ["*.json"])
                    songs = {}
                    for p, data in files.items():
                        if not p.endswith(".json"):
                            continue
                        j = json.loads(data)
                        for k, v in j.get("Entries", {}).items():
                            attrs = v.get("Attributes", {})
                            sk = attrs.get("SongKey", "")
                            sn = attrs.get("SongName", "")
                            sa = attrs.get("ArtistName", "")
                            arr = attrs.get("ArrangementName", "")
                            if sk and sn and arr not in ("Vocals", "ShowLights", "JVocals"):
                                if sk not in songs:
                                    songs[sk] = {"key": sk, "title": sn, "artist": sa, "arrangements": []}
                                songs[sk]["arrangements"].append(arr)
                    packs.append({
                        "name": name,
                        "filename": filename,
                        "song_count": len(songs),
                        "songs": sorted(songs.values(), key=lambda s: s["title"]),
                    })
                except Exception as e:
                    packs.append({"name": name, "filename": filename, "error": str(e)})

        # Count already extracted
        extracted = [f.name for f in dlc.iterdir()
                     if f.name.endswith("_p.psarc") and f.name not in
                     ("rs1compatibilitydlc_p.psarc", "rs1compatibilitydisc_p.psarc",
                      "rs1compatibilitydisc_m.psarc", "rs1compatibilitydisc_p.disabled.psarc")]

        return {
            "packs": packs,
            "has_songs_psarc": has_songs_psarc,
            "rs_dir": str(rs_dir) if rs_dir else None,
        }

    @app.websocket("/ws/plugins/rs1_extract/extract")
    async def ws_extract(websocket: WebSocket, pack: str = "all"):
        """Extract RS1 songs with progress."""
        await websocket.accept()

        dlc = _get_dlc_dir()
        if not dlc:
            await websocket.send_json({"error": "DLC folder not configured"})
            await websocket.close()
            return

        rs_dir = _find_rs_dir(dlc)

        progress_queue = asyncio.Queue()

        def _do_extract():
            try:
                from rs1_extractor import PsarcReader, process_pack, PACKS

                # Override paths
                songs_reader = None
                if rs_dir and (rs_dir / "songs.psarc").exists():
                    songs_reader = PsarcReader(str(rs_dir / "songs.psarc"))

                packs_to_run = []
                if pack in ("all", "dlc"):
                    cfg = PACKS["dlc"].copy()
                    cfg["psarc"] = dlc / "rs1compatibilitydlc_p.psarc"
                    if cfg["psarc"].exists():
                        packs_to_run.append(("dlc", cfg))
                if pack in ("all", "disc"):
                    cfg = PACKS["disc"].copy()
                    cfg["psarc"] = dlc / "rs1compatibilitydisc_p.psarc"
                    if cfg["psarc"].exists():
                        packs_to_run.append(("disc", cfg))

                total_extracted = 0
                for pack_name, config in packs_to_run:
                    progress_queue.put_nowait({
                        "stage": f"Processing RS1 {pack_name.upper()} pack...",
                        "progress": 5,
                    })

                    # Use the existing process_pack but with a progress callback
                    count = _extract_with_progress(
                        pack_name, config, songs_reader, dlc,
                        progress_queue,
                    )
                    total_extracted += count

                if songs_reader:
                    songs_reader.close()

                # Trigger library rescan for new files
                for f in dlc.iterdir():
                    if f.name.endswith("_p.psarc"):
                        stat = f.stat()
                        existing = _meta_db.get(f.name, stat.st_mtime, stat.st_size)
                        if not existing:
                            try:
                                meta = _extract_meta(f)
                                _meta_db.put(f.name, stat.st_mtime, stat.st_size, meta)
                            except Exception:
                                pass

                progress_queue.put_nowait({
                    "done": True,
                    "progress": 100,
                    "total": total_extracted,
                })

            except Exception as e:
                import traceback
                traceback.print_exc()
                progress_queue.put_nowait({"error": str(e)})

        def _extract_with_progress(pack_name, config, songs_reader, output_dir, queue):
            """Wrapper around process_pack that reports progress."""
            from rs1_extractor import (
                PsarcReader, parse_bnk_wem_id, get_song_info, sanitize_filename,
                build_hsan, build_aggregate_graph, update_xblock,
            )
            from patcher import pack_psarc
            import tempfile

            psarc_path = config["psarc"]
            manifest_dir = config["manifest_dir"]
            appid = config["appid"]
            audio_self_contained = pack_name == "disc"

            reader = PsarcReader(str(psarc_path))

            xblock_files = {
                name: name.rsplit("/", 1)[-1]
                for name in reader.list_files()
                if name.startswith("gamexblocks/nsongs/") and name.endswith(".xblock")
            }
            song_keys = [(fname.replace("_fcp_dlc.xblock", "").replace(".xblock", ""), path, fname)
                         for path, fname in sorted(xblock_files.items())]

            flat_root = reader.get("flatmodels/rs/rsenumerable_root.flat")
            flat_song = reader.get("flatmodels/rs/rsenumerable_song.flat")
            hsan_path = f"manifests/{manifest_dir}/{manifest_dir}.hsan"
            hsan_raw = reader.get(hsan_path)
            hsan_data = json.loads(hsan_raw) if hsan_raw else {"Entries": {}}
            hsan_entries = hsan_data.get("Entries", {})

            audio_bnks = {}
            if not audio_self_contained and songs_reader:
                for key, _, _ in song_keys:
                    for pat in [f"audio/windows/song_{key}.bnk", f"audio/windows/song_{key}_preview.bnk"]:
                        data = songs_reader.get(pat)
                        if data:
                            audio_bnks[pat] = data

            extracted = 0
            total = len(song_keys)

            for i, (key, xblock_path, xblock_fname) in enumerate(song_keys):
                pct = int(5 + (i / max(total, 1)) * 90)
                manifests = reader.get_matching([f"manifests/{manifest_dir}/{key}_*.json"])
                sngs = reader.get_matching([f"songs/bin/generic/{key}_*.sng"])
                album_art = reader.get_matching([f"gfxassets/album_art/album_{key}_*.dds"])
                showlights = reader.get(f"songs/arr/{key}_showlights.xml")
                xblock_data = reader.get(xblock_path)

                if not manifests:
                    continue

                info = None
                for mpath, mdata in sorted(manifests.items()):
                    if "_vocals" not in mpath:
                        info = get_song_info(mdata)
                        break
                if not info:
                    info = get_song_info(list(manifests.values())[0])

                queue.put_nowait({
                    "stage": f"[{i+1}/{total}] {info['artist']} - {info['title']}",
                    "progress": pct,
                })

                artist = sanitize_filename(info["artist"])
                title = sanitize_filename(info["title"])
                out_name = f"{title} - {artist}_p.psarc"

                # Skip if already extracted
                if (output_dir / out_name).exists():
                    extracted += 1
                    continue

                song_bnk_name = f"audio/windows/song_{key}.bnk"
                preview_bnk_name = f"audio/windows/song_{key}_preview.bnk"

                if audio_self_contained:
                    song_bnk = reader.get(song_bnk_name)
                    preview_bnk = reader.get(preview_bnk_name)
                else:
                    song_bnk = audio_bnks.get(song_bnk_name)
                    preview_bnk = audio_bnks.get(preview_bnk_name)

                if not song_bnk:
                    continue

                song_wem_id = parse_bnk_wem_id(song_bnk)
                preview_wem_id = parse_bnk_wem_id(preview_bnk) if preview_bnk else None

                wem_files = {}
                if song_wem_id:
                    wem_name = f"audio/windows/{song_wem_id}.wem"
                    wem_data = reader.get(wem_name) if audio_self_contained else songs_reader.get(wem_name)
                    if wem_data:
                        wem_files[wem_name] = wem_data

                if preview_wem_id and preview_wem_id != song_wem_id:
                    wem_name = f"audio/windows/{preview_wem_id}.wem"
                    wem_data = reader.get(wem_name) if audio_self_contained else songs_reader.get(wem_name)
                    if wem_data:
                        wem_files[wem_name] = wem_data

                if not wem_files:
                    continue

                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir = Path(tmpdir)
                    dlc_key = f"songs_dlc_{key}"

                    (tmpdir / "appid.appid").write_text(appid)

                    audio_dir = tmpdir / "audio" / "windows"
                    audio_dir.mkdir(parents=True)
                    (audio_dir / f"song_{key}.bnk").write_bytes(song_bnk)
                    if preview_bnk:
                        (audio_dir / f"song_{key}_preview.bnk").write_bytes(preview_bnk)
                    for wem_path, wem_data in wem_files.items():
                        (audio_dir / wem_path.rsplit("/", 1)[-1]).write_bytes(wem_data)

                    flat_dir = tmpdir / "flatmodels" / "rs"
                    flat_dir.mkdir(parents=True)
                    if flat_root:
                        (flat_dir / "rsenumerable_root.flat").write_bytes(flat_root)
                    if flat_song:
                        (flat_dir / "rsenumerable_song.flat").write_bytes(flat_song)

                    xblock_dir = tmpdir / "gamexblocks" / "nsongs"
                    xblock_dir.mkdir(parents=True)
                    (xblock_dir / xblock_fname).write_bytes(
                        update_xblock(xblock_data, manifest_dir, dlc_key))

                    art_dir = tmpdir / "gfxassets" / "album_art"
                    art_dir.mkdir(parents=True)
                    for art_path, art_data in album_art.items():
                        (art_dir / art_path.rsplit("/", 1)[-1]).write_bytes(art_data)

                    manifest_out_dir = tmpdir / "manifests" / dlc_key
                    manifest_out_dir.mkdir(parents=True)
                    manifest_names = []
                    for mpath, mdata in manifests.items():
                        mfname = mpath.rsplit("/", 1)[-1]
                        manifest_names.append(mfname.replace(".json", ""))
                        (manifest_out_dir / mfname).write_bytes(mdata)

                    (manifest_out_dir / f"{dlc_key}.hsan").write_text(
                        build_hsan(manifests, hsan_entries, key))

                    arr_dir = tmpdir / "songs" / "arr"
                    arr_dir.mkdir(parents=True)
                    if showlights:
                        (arr_dir / f"{key}_showlights.xml").write_bytes(showlights)

                    sng_dir = tmpdir / "songs" / "bin" / "generic"
                    sng_dir.mkdir(parents=True)
                    sng_names = []
                    for sng_path, sng_data in sngs.items():
                        sng_fname = sng_path.rsplit("/", 1)[-1]
                        sng_names.append(sng_fname.replace(".sng", ""))
                        (sng_dir / sng_fname).write_bytes(sng_data)

                    dds_names = [p.rsplit("/", 1)[-1].replace(".dds", "") for p in album_art]

                    (tmpdir / f"{key}_aggregategraph.nt").write_text(
                        build_aggregate_graph(key, manifest_names, sng_names, dds_names,
                                              showlights is not None, xblock_fname))

                    pack_psarc(tmpdir, output_dir / out_name)
                    extracted += 1

            reader.close()
            return extracted

        loop = asyncio.get_event_loop()
        task = loop.run_in_executor(None, _do_extract)

        try:
            while True:
                try:
                    msg = await asyncio.wait_for(progress_queue.get(), timeout=2.0)
                    await websocket.send_json(msg)
                    if msg.get("done") or msg.get("error"):
                        break
                except asyncio.TimeoutError:
                    if task.done():
                        break
        except WebSocketDisconnect:
            pass

        await websocket.close()
