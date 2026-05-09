// RS1 Song Extractor plugin

(function() {
    // Idempotency: if screen.js is re-evaluated (loader cache miss, hot reload,
    // older core builds without the load-side guard), don't re-wrap showScreen —
    // each re-wrap captures the previous wrapper, growing the chain and
    // leaking closures.
    const HOOK_KEY = '__slopsmithRs1ExtractHooksInstalled';
    if (window[HOOK_KEY]) return;

    const origShowScreen = window.showScreen;
    if (typeof origShowScreen !== 'function') return;
    window.showScreen = function(id) {
        origShowScreen(id);
        if (id === 'plugin-rs1_extract') rs1LoadStatus();
    };
    window[HOOK_KEY] = true;
})();

async function rs1LoadStatus() {
    const status = document.getElementById('rs1-status');
    const packs = document.getElementById('rs1-packs');
    document.getElementById('rs1-progress').classList.add('hidden');
    document.getElementById('rs1-result').classList.add('hidden');

    status.innerHTML = '<p class="text-gray-500 text-sm">Loading...</p>';

    try {
        const resp = await fetch('/api/plugins/rs1_extract/status');
        const data = await resp.json();

        if (data.error) {
            status.innerHTML = `<p class="text-red-400 text-sm">${data.error}</p>`;
            return;
        }

        if (!data.has_songs_psarc) {
            status.innerHTML = `
                <div class="bg-yellow-900/20 border border-yellow-800/30 rounded-xl p-4 text-sm">
                    <p class="text-yellow-400 font-semibold">songs.psarc not found</p>
                    <p class="text-gray-400 mt-1">The Rocksmith install directory needs to be accessible. Make sure the DLC folder path is set correctly in Settings (should be inside the Rocksmith2014 folder).</p>
                </div>`;
        } else {
            status.innerHTML = `
                <div class="bg-dark-700/50 border border-gray-800/50 rounded-xl p-3 text-xs text-gray-500">
                    Rocksmith found at: ${esc(data.rs_dir)}
                </div>`;
        }

        if (data.packs.length === 0) {
            packs.innerHTML = '<p class="text-gray-500 text-sm">No RS1 compatibility packs found in your DLC folder.</p>';
            return;
        }

        packs.innerHTML = data.packs.map(p => {
            if (p.error) {
                return `<div class="bg-red-900/20 border border-red-800/30 rounded-xl p-4">
                    <p class="text-red-400">${esc(p.name)}: ${esc(p.error)}</p>
                </div>`;
            }
            return `<div class="bg-dark-700 border border-gray-800 rounded-xl p-5">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h3 class="text-lg font-semibold text-white">RS1 ${esc(p.name)} Pack</h3>
                        <p class="text-xs text-gray-500">${p.song_count} songs · ${esc(p.filename)}</p>
                    </div>
                    <button onclick="rs1Extract('${p.name.toLowerCase()}')"
                        class="bg-accent hover:bg-accent-light px-5 py-2 rounded-xl text-sm font-semibold text-white transition">
                        Extract All
                    </button>
                </div>
                <div class="max-h-64 overflow-y-auto space-y-1">
                    ${p.songs.map(s => `
                        <div class="flex items-center justify-between py-1.5 px-3 rounded-lg hover:bg-dark-600/50 text-sm">
                            <div class="min-w-0">
                                <span class="text-white">${esc(s.title)}</span>
                                <span class="text-gray-500 ml-2">${esc(s.artist)}</span>
                            </div>
                            <span class="text-xs text-gray-600 flex-shrink-0">${s.arrangements.join(', ')}</span>
                        </div>
                    `).join('')}
                </div>
            </div>`;
        }).join('');

        // Add "Extract All Packs" button if multiple
        if (data.packs.length > 1) {
            packs.innerHTML += `
                <button onclick="rs1Extract('all')"
                    class="w-full bg-accent hover:bg-accent-light px-5 py-3 rounded-xl text-sm font-semibold text-white transition">
                    Extract All Packs
                </button>`;
        }
    } catch (e) {
        status.innerHTML = `<p class="text-red-400 text-sm">Failed to load: ${e}</p>`;
    }
}

function rs1Extract(pack) {
    document.getElementById('rs1-packs').classList.add('hidden');
    document.getElementById('rs1-progress').classList.remove('hidden');
    document.getElementById('rs1-result').classList.add('hidden');
    document.getElementById('rs1-bar').style.width = '0%';
    document.getElementById('rs1-stage').textContent = 'Connecting...';

    const ws = new WebSocket(`ws://${location.host}/ws/plugins/rs1_extract/extract?pack=${pack}`);
    ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.progress !== undefined)
            document.getElementById('rs1-bar').style.width = msg.progress + '%';
        if (msg.stage)
            document.getElementById('rs1-stage').textContent = msg.stage;
        if (msg.done) {
            document.getElementById('rs1-progress').classList.add('hidden');
            document.getElementById('rs1-result').classList.remove('hidden');
            document.getElementById('rs1-result').innerHTML = `
                <div class="bg-green-900/20 border border-green-800/30 rounded-xl p-5 text-center">
                    <p class="text-green-400 font-semibold text-lg mb-1">Extraction Complete!</p>
                    <p class="text-gray-400">${msg.total} songs extracted to your DLC folder</p>
                    <button onclick="rs1LoadStatus()" class="mt-4 px-4 py-2 bg-dark-600 hover:bg-dark-500 rounded-xl text-sm text-gray-300 transition">Back</button>
                </div>`;
        }
        if (msg.error) {
            document.getElementById('rs1-progress').classList.add('hidden');
            document.getElementById('rs1-result').classList.remove('hidden');
            document.getElementById('rs1-result').innerHTML = `
                <div class="bg-red-900/20 border border-red-800/30 rounded-xl p-5 text-center">
                    <p class="text-red-400 font-semibold mb-1">Extraction Failed</p>
                    <p class="text-gray-400 text-sm">${msg.error}</p>
                    <button onclick="rs1LoadStatus()" class="mt-4 px-4 py-2 bg-dark-600 hover:bg-dark-500 rounded-xl text-sm text-gray-300 transition">Back</button>
                </div>`;
        }
    };
    ws.onerror = () => {
        document.getElementById('rs1-stage').textContent = 'Connection lost';
    };
}
