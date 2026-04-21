/**
 * KaraoKing - Lecteur avec mode karaoké
 * Utilise deux pistes audio (original + instrumental) avec fondu croisé.
 */

class KaraokePlayer {
    constructor() {
        // Web Audio engine — single AudioContext, two AudioBufferSourceNodes
        // started at the same audioCtx time. No drift, no race between two
        // independent <audio> decoders.
        this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        this.gainV = this.audioCtx.createGain();
        this.gainI = this.audioCtx.createGain();
        this.gainMaster = this.audioCtx.createGain();
        this.gainV.connect(this.gainMaster);
        this.gainI.connect(this.gainMaster);
        this.gainMaster.connect(this.audioCtx.destination);

        this.bufV = null;        // AudioBuffer (vocals or original)
        this.bufI = null;        // AudioBuffer (instrumental)
        this.srcV = null;        // current BufferSourceNode
        this.srcI = null;
        this.startCtxTime = 0;   // audioCtx.currentTime at start
        this.startOffset = 0;    // offset into the buffer at start

        // State
        this.songs = [];
        this.currentSong = null;
        this.lyrics = [];
        this.currentLineIndex = -1;
        this.isPlaying = false;
        this.isSeeking = false;
        this.hasInstrumental = false;
        this._playToken = 0;

        // DOM
        this.songListView = document.getElementById('songListView');
        this.nowPlayingView = document.getElementById('nowPlayingView');
        this.songList = document.getElementById('songList');
        this.songTitle = document.getElementById('songTitle');
        this.songArtist = document.getElementById('songArtist');
        this.coverArt = document.getElementById('coverArt');
        this.bgGradient = document.getElementById('bgGradient');
        this.lyricsScroll = document.getElementById('lyricsScroll');
        this.lyricsSection = document.getElementById('lyricsSection');
        this.progressBar = document.getElementById('progressBar');
        this.progressPlayed = document.getElementById('progressPlayed');
        this.progressThumb = document.getElementById('progressThumb');
        this.currentTimeEl = document.getElementById('currentTime');
        this.totalTimeEl = document.getElementById('totalTime');
        this.playBtn = document.getElementById('playBtn');
        this.playIcon = document.getElementById('playIcon');
        this.prevSongBtn = document.getElementById('prevSongBtn');
        this.nextSongBtn = document.getElementById('nextSongBtn');
        this.seekBackBtn = document.getElementById('seekBackBtn');
        this.seekFwdBtn = document.getElementById('seekFwdBtn');
        this.volumeSlider = document.getElementById('volumeSlider');
        this.vocalsSlider = document.getElementById('vocalsSlider');
        this.instrumentalSlider = document.getElementById('instrumentalSlider');
        this.trackSlidersContainer = document.getElementById('trackSlidersContainer');
        this.nowPlayingLabel = document.getElementById('nowPlayingLabel');
        this.backBtn = document.getElementById('backBtn');

        this.init();
    }

    init() {
        this.loadSongs().then(() => {
            const params = new URLSearchParams(window.location.search);
            const playId = params.get('play');
            if (playId && this.songs.find(s => s.id === playId)) {
                this.selectSong(playId);
                window.history.replaceState({}, '', '/');
            }
        });
        this.bindEvents();
        this._tick();
    }

    /** Escape HTML to prevent XSS */
    _esc(str) {
        if (!str) return '';
        return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }

    // ─── Web Audio engine ───────────────────────────────────────────────────

    async _fetchAudioBuffer(url) {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error('fetch ' + resp.status);
        const arr = await resp.arrayBuffer();
        return await this.audioCtx.decodeAudioData(arr);
    }

    _stopSources() {
        for (const s of [this.srcV, this.srcI]) {
            if (!s) continue;
            try { s.onended = null; s.stop(); } catch {}
            try { s.disconnect(); } catch {}
        }
        this.srcV = null;
        this.srcI = null;
    }

    _startAt(offset) {
        this._stopSources();
        if (!this.bufV) return;
        const when = this.audioCtx.currentTime + 0.05;

        this.srcV = this.audioCtx.createBufferSource();
        this.srcV.buffer = this.bufV;
        this.srcV.connect(this.gainV);

        if (this.hasInstrumental && this.bufI) {
            this.srcI = this.audioCtx.createBufferSource();
            this.srcI.buffer = this.bufI;
            this.srcI.connect(this.gainI);
        }

        this.srcV.start(when, offset);
        if (this.srcI) this.srcI.start(when, offset);

        this.startCtxTime = when;
        this.startOffset = offset;
        this.isPlaying = true;
        this.updatePlayIcon();

        this.srcV.onended = () => {
            if (!this.isPlaying) return;
            if (this._currentTime() >= this._duration() - 0.1) {
                this.isPlaying = false;
                this.updatePlayIcon();
                this.nextSong(true);
            }
        };
    }

    _duration() { return this.bufV ? this.bufV.duration : 0; }

    _currentTime() {
        if (!this.bufV) return 0;
        if (this.isPlaying) {
            return Math.min(this._duration(), this.startOffset + (this.audioCtx.currentTime - this.startCtxTime));
        }
        return this.startOffset;
    }

    _tick() {
        if (!this.isSeeking) {
            const t = this._currentTime();
            const d = this._duration() || 1;
            const pct = (t / d) * 100;
            this.progressPlayed.style.width = pct + '%';
            this.progressThumb.style.left = pct + '%';
            this.currentTimeEl.textContent = this.formatTime(t);
            this.totalTimeEl.textContent = this.formatTime(this._duration());
            this.updateLyricsHighlight(t);
        }
        requestAnimationFrame(() => this._tick());
    }

    bindEvents() {
        // Back to song list
        this.backBtn.addEventListener('click', () => this.showSongList());

        // Playback
        this.playBtn.addEventListener('click', () => this.togglePlay());
        this.seekBackBtn.addEventListener('click', () => this.seekRelative(-10));
        this.seekFwdBtn.addEventListener('click', () => this.seekRelative(10));
        this.prevSongBtn.addEventListener('click', () => this.prevSong());
        this.nextSongBtn.addEventListener('click', () => this.nextSong());

        // Volume
        this.volumeSlider.addEventListener('input', (e) => this.setVolume(e.target.value));

        // Track sliders → per-track gain nodes
        this.vocalsSlider.addEventListener('input', (e) => { this.gainV.gain.value = e.target.value / 100; });
        this.instrumentalSlider.addEventListener('input', (e) => { this.gainI.gain.value = e.target.value / 100; });

        // Progress bar seeking
        this.progressBar.addEventListener('mousedown', (e) => this.startSeek(e));
        this.progressBar.addEventListener('touchstart', (e) => this.startSeek(e), { passive: false });
    }

    // ─── SONG LIST ──────────────────────────────────────────────────────────

    async loadSongs() {
        try {
            const resp = await fetch('/api/songs');
            this.songs = await resp.json();
            this.renderSongList();
        } catch (err) {
            console.error('Failed to load songs', err);
        }
    }

    renderSongList() {
        const hasSongs = this.songs.length > 0;

        // Show/hide sections
        const searchWrap = document.getElementById('searchBarWrap');
        const statsBar = document.getElementById('statsBar');
        const karaokeSection = document.getElementById('karaokeSection');
        const heroSection = document.getElementById('heroSection');

        // Always show search bar so users can search YouTube
        if (searchWrap) searchWrap.style.display = '';

        if (!hasSongs) {
            this.songList.innerHTML = `
                <div class="empty-library">
                    <div class="empty-icon-wrap">
                        <i class="fas fa-record-vinyl"></i>
                    </div>
                    <h3>Aucune chanson disponible</h3>
                    <p>Recherchez une chanson pour la telecharger depuis YouTube</p>
                </div>`;
            if (statsBar) statsBar.style.display = 'none';
            if (karaokeSection) karaokeSection.style.display = 'none';
            this._setupSearch();
            return;
        }

        // Show search & stats
        if (searchWrap) searchWrap.style.display = '';
        if (statsBar) statsBar.style.display = '';

        // Stats
        const totalSongs = this.songs.length;
        const karaokeSongs = this.songs.filter(s => s.has_instrumental && s.has_lyrics);
        const lyricsSongs = this.songs.filter(s => s.has_lyrics);

        const statTotal = document.getElementById('statTotal');
        const statKaraoke = document.getElementById('statKaraoke');
        const statLyrics = document.getElementById('statLyrics');
        if (statTotal) statTotal.textContent = totalSongs;
        if (statKaraoke) statKaraoke.textContent = karaokeSongs.length;
        if (statLyrics) statLyrics.textContent = lyricsSongs.length;

        // Karaoke ready section (horizontal scroll cards)
        if (karaokeSongs.length > 0 && karaokeSection) {
            karaokeSection.style.display = '';
            const karaokeBadge = document.getElementById('karaokeBadge');
            if (karaokeBadge) karaokeBadge.textContent = karaokeSongs.length;

            const karaokeCards = document.getElementById('karaokeCards');
            if (karaokeCards) {
                karaokeCards.innerHTML = karaokeSongs.map(song => `
                    <div class="song-card" data-id="${this._esc(song.id)}">
                        <div class="song-card-cover">
                            ${song.has_cover
                                ? `<img src="/api/cover/${this._esc(song.id)}" alt="">`
                                : `<div class="cover-placeholder-card"><i class="fas fa-microphone-alt"></i></div>`}
                            <div class="song-card-play"><i class="fas fa-play"></i></div>
                        </div>
                        <div class="song-card-title">${this._esc(this._formatTitle(song.title))}</div>
                        <div class="song-card-artist">${this._esc(song.artist || 'Artiste inconnu')}</div>
                    </div>
                `).join('');

                karaokeCards.querySelectorAll('.song-card').forEach(el => {
                    el.addEventListener('click', () => this.selectSong(el.dataset.id));
                });
            }
        } else if (karaokeSection) {
            karaokeSection.style.display = 'none';
        }

        // Update hero subtitle if songs exist
        if (heroSection) {
            const sub = heroSection.querySelector('.hero-subtitle');
            if (sub) sub.textContent = `${totalSongs} chanson${totalSongs > 1 ? 's' : ''} disponible${totalSongs > 1 ? 's' : ''} — choisissez et chantez !`;
        }

        // All songs grid
        this.songList.innerHTML = this.songs.map(song => `
            <div class="song-grid-item" data-id="${this._esc(song.id)}">
                <div class="song-grid-cover">
                    ${song.has_cover
                        ? `<img src="/api/cover/${this._esc(song.id)}" alt="">`
                        : `<div class="cover-placeholder-grid"><i class="fas fa-music"></i></div>`}
                    <div class="song-grid-play"><i class="fas fa-play"></i></div>
                    ${song.has_instrumental ? '<span class="karaoke-badge-grid">K</span>' : ''}
                    ${song.has_lyrics ? '<span class="lyrics-badge-grid"><i class="fas fa-align-left"></i></span>' : ''}
                </div>
                <div class="song-grid-title">${this._esc(this._formatTitle(song.title))}</div>
                <div class="song-grid-artist">${this._esc(song.artist || 'Artiste inconnu')}</div>
            </div>
        `).join('');

        // Bind click events
        this.songList.querySelectorAll('.song-grid-item').forEach(el => {
            el.addEventListener('click', () => this.selectSong(el.dataset.id));
        });

        // Setup search
        this._setupSearch();
    }

    _formatTitle(str) {
        return str.replace(/_/g, ' ').replace(/\s*-\s*/g, ' - ').replace(/\s+/g, ' ').trim();
    }

    _setupSearch() {
        const input = document.getElementById('searchInput');
        const clearBtn = document.getElementById('searchClear');
        if (!input) return;

        this._ytSearchTimeout = null;

        input.addEventListener('input', () => {
            const q = input.value.toLowerCase().trim();
            if (clearBtn) clearBtn.style.display = q ? '' : 'none';

            // Filter all songs grid
            let visibleCount = 0;
            this.songList.querySelectorAll('.song-grid-item').forEach(el => {
                const id = el.dataset.id;
                const song = this.songs.find(s => s.id === id);
                if (!song) return;
                const match = !q || song.title.toLowerCase().includes(q) || (song.artist || '').toLowerCase().includes(q);
                el.style.display = match ? '' : 'none';
                if (match) visibleCount++;
            });

            // Filter karaoke cards
            const karaokeCards = document.getElementById('karaokeCards');
            if (karaokeCards) {
                karaokeCards.querySelectorAll('.song-card').forEach(el => {
                    const id = el.dataset.id;
                    const song = this.songs.find(s => s.id === id);
                    if (!song) return;
                    const match = !q || song.title.toLowerCase().includes(q) || (song.artist || '').toLowerCase().includes(q);
                    el.style.display = match ? '' : 'none';
                });
            }

            // Show YouTube search section when no local results
            this._updateYtSection(q, visibleCount);
        });

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                input.value = '';
                input.dispatchEvent(new Event('input'));
                input.focus();
            });
        }
    }

    _updateYtSection(query, visibleCount) {
        let ytSection = document.getElementById('ytSearchSection');

        if (!query) {
            if (ytSection) ytSection.style.display = 'none';
            return;
        }

        // Create YouTube section if doesn't exist
        if (!ytSection) {
            ytSection = document.createElement('div');
            ytSection.id = 'ytSearchSection';
            ytSection.className = 'home-section yt-search-section';
            const allSongsSection = document.getElementById('allSongsSection');
            allSongsSection.parentNode.insertBefore(ytSection, allSongsSection.nextSibling);
        }

        ytSection.style.display = '';

        if (visibleCount > 0) {
            // There are local results, show subtle YouTube option
            ytSection.innerHTML = `
                <div class="yt-search-hint">
                    <span>Pas ce que vous cherchez ?</span>
                    <button class="btn-yt-search" id="ytSearchBtn">
                        <i class="fas fa-search"></i> Recherche Avancé
                    </button>
                </div>`;
        } else {
            // No local results, show prominent YouTube search
            ytSection.innerHTML = `
                <div class="yt-no-results">
                    <i class="fas fa-search"></i>
                    <p>Aucun résultat local pour « <strong>${this._esc(query)}</strong> »</p>
                    <button class="btn-yt-search btn-yt-prominent" id="ytSearchBtn">
                        <i class="fab fa-youtube"></i> Recherche Avancé
                    </button>
                </div>
                <div class="yt-results" id="ytResults"></div>`;
        }

        const btn = document.getElementById('ytSearchBtn');
        if (btn) {
            btn.addEventListener('click', () => {
                const q = document.getElementById('searchInput').value.trim();
                if (q) this._searchYouTube(q);
            });
        }
    }

    async _searchYouTube(query) {
        const ytResults = document.getElementById('ytResults') || (() => {
            const div = document.createElement('div');
            div.id = 'ytResults';
            div.className = 'yt-results';
            document.getElementById('ytSearchSection').appendChild(div);
            return div;
        })();

        ytResults.innerHTML = `
            <div class="yt-loading">
                <i class="fas fa-spinner fa-spin"></i> Recherche YouTube...
            </div>`;

        try {
            const resp = await fetch(`/api/yt-search?q=${encodeURIComponent(query)}`);
            const results = await resp.json();

            if (!resp.ok || !results.length) {
                ytResults.innerHTML = '<p class="yt-empty">Aucun résultat YouTube</p>';
                return;
            }

            ytResults.innerHTML = results.map(r => `
                <div class="yt-result-item" data-url="${this._esc(r.url)}">
                    <div class="yt-result-thumb">
                        ${r.thumbnail ? `<img src="${this._esc(r.thumbnail)}" alt="">` : '<i class="fas fa-music"></i>'}
                        <span class="yt-result-duration">${this._formatDuration(r.duration)}</span>
                    </div>
                    <div class="yt-result-info">
                        <div class="yt-result-title">${this._esc(r.title)}</div>
                        <div class="yt-result-channel">${this._esc(r.channel)}</div>
                    </div>
                    <button class="btn-yt-download" title="Télécharger">
                        <i class="fas fa-download"></i>
                    </button>
                </div>
            `).join('');

            // Bind download buttons
            ytResults.querySelectorAll('.yt-result-item').forEach(el => {
                const dlBtn = el.querySelector('.btn-yt-download');
                dlBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this._downloadFromYouTube(el.dataset.url, dlBtn);
                });
            });

        } catch (err) {
            ytResults.innerHTML = '<p class="yt-empty">Erreur de recherche YouTube</p>';
        }
    }

    async _downloadFromYouTube(url, btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        try {
            const resp = await fetch('/api/yt-download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            const data = await resp.json();

            if (!resp.ok) {
                btn.innerHTML = '<i class="fas fa-times"></i>';
                btn.title = data.error || 'Erreur';
                return;
            }

            btn.innerHTML = '<i class="fas fa-check"></i>';
            btn.classList.add('btn-yt-done');
            btn.title = 'Ajouté !';

            // Reload songs and optionally play the new song
            await this.loadSongs();

            // Auto-play the downloaded song
            if (data.song_id) {
                this.selectSong(data.song_id);
                setTimeout(() => this.play(), 500);
            }

        } catch (err) {
            btn.innerHTML = '<i class="fas fa-times"></i>';
            btn.disabled = false;
        }
    }

    _formatDuration(seconds) {
        if (!seconds) return '';
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}:${s.toString().padStart(2, '0')}`;
    }

    showSongList() {
        this.songListView.style.display = '';
        this.nowPlayingView.style.display = 'none';
        this.nowPlayingLabel.textContent = 'KaraoKing';
    }

    // ─── SONG LOADING ───────────────────────────────────────────────────────

    async selectSong(songId) {
        const song = this.songs.find(s => s.id === songId);
        if (!song) return;

        const myToken = ++this._playToken;

        // Stop current playback and clear buffers
        this._stopSources();
        this.bufV = null;
        this.bufI = null;
        this.hasInstrumental = false;
        this.startOffset = 0;
        this.isPlaying = false;
        this.updatePlayIcon();

        this.currentSong = song;

        // Update UI
        this.songTitle.textContent = song.title;
        this.songArtist.textContent = song.artist || 'Artiste inconnu';
        this.nowPlayingLabel.textContent = song.title;

        if (song.has_cover) {
            this.coverArt.innerHTML = `<img src="/api/cover/${this._esc(song.id)}" alt="${this._esc(song.title)}">`;
        } else {
            this.coverArt.innerHTML = '<i class="fas fa-music"></i>';
        }
        this.updateBackground(song);

        // Reset gains
        this.gainV.gain.value = 1;
        this.gainI.gain.value = 1;
        this.vocalsSlider.value = 100;
        this.instrumentalSlider.value = 100;

        // Decode the audio buffers — single decoder = perfect sync between tracks
        try {
            if (song.has_vocals && song.has_instrumental) {
                const [vBuf, iBuf] = await Promise.all([
                    this._fetchAudioBuffer(`/api/audio/${song.id}/vocals`),
                    this._fetchAudioBuffer(`/api/audio/${song.id}/instrumental`),
                ]);
                if (myToken !== this._playToken) return;
                this.bufV = vBuf;
                this.bufI = iBuf;
                this.hasInstrumental = true;
                this.trackSlidersContainer.classList.remove('disabled');
            } else {
                const buf = await this._fetchAudioBuffer(`/api/audio/${song.id}/original`);
                if (myToken !== this._playToken) return;
                this.bufV = buf;
                this.hasInstrumental = false;
                this.trackSlidersContainer.classList.add('disabled');
            }
        } catch (e) {
            console.error('audio decode failed', e);
            return;
        }

        await this.loadLyrics(song.id);
        if (myToken !== this._playToken) return;

        // Load global ad banner
        try {
            const adResp = await fetch('/api/ads/active');
            const ad = await adResp.json();
            if (ad.text) {
                // Remove previous banner
                const prevBanner = this.lyricsScroll.previousElementSibling;
                if (prevBanner && prevBanner.classList.contains('ad-banner')) {
                    prevBanner.remove();
                }
                // Add new banner
                const banner = document.createElement('div');
                banner.className = 'ad-banner';
                banner.textContent = ad.text;
                banner.innerHTML = ad.text.replace(/\\n/g, '<br>');
                this.lyricsScroll.parentNode.insertBefore(banner, this.lyricsScroll);
            }
        } catch (e) {
            console.log('No ad banner');
        }

        this.songListView.style.display = 'none';
        this.nowPlayingView.style.display = '';
        this._updateListHighlight();
        this.currentLineIndex = -1;

        // Auto-play
        if (this.audioCtx.state === 'suspended') {
            try { await this.audioCtx.resume(); } catch {}
        }
        this._startAt(0);
    }

    async loadLyrics(songId) {
        try {
            const resp = await fetch(`/api/lyrics/${songId}`);
            if (!resp.ok) throw new Error('No lyrics');
            const data = await resp.json();
            this.lyrics = data.segments || [];
        } catch {
            this.lyrics = [];
        }
        this.renderLyrics();
    }

    renderLyrics() {
        const spacerTop = '<div class="lyrics-spacer"></div>';
        const spacerBottom = '<div class="lyrics-spacer"></div>';

        if (!this.lyrics.length) {
            this.lyricsScroll.innerHTML = spacerTop +
                '<p class="lyrics-line lyrics-placeholder">Pas de paroles disponibles</p>' +
                spacerBottom;
            return;
        }

        // Pre-compute word timings for each line
        this.wordTimings = [];

        const linesHtml = this.lyrics.map((line, i) => {
            const lineStart = line.time;
            const lineEnd = (i < this.lyrics.length - 1) ? this.lyrics[i + 1].time : (line.end_time || lineStart + 5);
            const words = line.text.split(/\s+/).filter(w => w.length > 0);

            if (words.length === 0) {
                this.wordTimings.push([]);
                return `<p class="lyrics-line" data-index="${i}"></p>`;
            }

            // Interpolate word timings based on character length
            const totalChars = words.reduce((sum, w) => sum + w.length, 0);
            const duration = lineEnd - lineStart;
            let elapsed = 0;
            const timings = [];

            const wordsHtml = words.map((word, wi) => {
                const wordStart = lineStart + (elapsed / totalChars) * duration;
                const wordEnd = lineStart + ((elapsed + word.length) / totalChars) * duration;
                elapsed += word.length;
                timings.push({ start: wordStart, end: wordEnd });
                return `<span class="lyrics-word" data-line="${i}" data-word="${wi}">${this._esc(word)}</span>`;
            }).join(' ');

            this.wordTimings.push(timings);
            return `<p class="lyrics-line" data-index="${i}">${wordsHtml}</p>`;
        }).join('');

        this.lyricsScroll.innerHTML = spacerTop + linesHtml + spacerBottom;
    }

    updateBackground(song) {
        // Generate a nice gradient based on song (pseudo-random from id)
        const hue = this.hashCode(song.id) % 360;
        this.bgGradient.style.background = `
            linear-gradient(
                180deg,
                hsl(${hue}, 30%, 92%) 0%,
                hsl(${hue}, 15%, 96%) 60%,
                #f5f5f7 100%
            )`;
    }

    hashCode(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
        }
        return Math.abs(hash);
    }

    // ─── PLAYBACK ───────────────────────────────────────────────────────────

    async togglePlay() {
        if (!this.bufV) return;
        if (this.audioCtx.state === 'suspended') {
            try { await this.audioCtx.resume(); } catch {}
        }
        if (this.isPlaying) this.pause();
        else this.play();
    }

    play() {
        if (!this.bufV) return;
        this._startAt(this.startOffset);
    }

    pause() {
        if (!this.isPlaying) return;
        const pos = this._currentTime();
        this._stopSources();
        this.startOffset = pos;
        this.isPlaying = false;
        this.updatePlayIcon();
    }

    updatePlayIcon() {
        this.playIcon.className = this.isPlaying ? 'fas fa-pause' : 'fas fa-play';
    }

    seekRelative(seconds) {
        if (!this.bufV) return;
        const newTime = Math.max(0, Math.min(this._duration(), this._currentTime() + seconds));
        if (this.isPlaying) this._startAt(newTime);
        else this.startOffset = newTime;
    }

    setVolume(val) {
        // Master volume × per-track gains
        const v = val / 100;
        this.gainMaster.gain.value = v;
    }

    nextSong() {
        if (!this.currentSong) return;
        const idx = this.songs.findIndex(s => s.id === this.currentSong.id);
        if (idx < this.songs.length - 1) {
            this.selectSong(this.songs[idx + 1].id);
        }
    }

    prevSong() {
        if (!this.currentSong) return;
        // If more than 3 seconds in, restart the song
        if (this._currentTime() > 3) {
            if (this.isPlaying) this._startAt(0);
            else this.startOffset = 0;
            return;
        }
        const idx = this.songs.findIndex(s => s.id === this.currentSong.id);
        if (idx > 0) {
            this.selectSong(this.songs[idx - 1].id);
        }
    }

    _updateListHighlight() {
        const currentId = this.currentSong ? this.currentSong.id : null;
        this.songList.querySelectorAll('.song-list-row').forEach(row => {
            row.classList.toggle('is-playing', row.dataset.id === currentId);
        });
    }

    // ─── SEEKING ────────────────────────────────────────────────────────────

    startSeek(e) {
        e.preventDefault();
        if (!this.bufV) return;
        this.isSeeking = true;

        const onMove = (ev) => {
            const rect = this.progressBar.getBoundingClientRect();
            const clientX = ev.touches ? ev.touches[0].clientX : ev.clientX;
            let pct = (clientX - rect.left) / rect.width;
            pct = Math.max(0, Math.min(1, pct));

            this.progressPlayed.style.width = (pct * 100) + '%';
            this.progressThumb.style.left = (pct * 100) + '%';
            this.currentTimeEl.textContent = this.formatTime(pct * this._duration());
        };

        const onEnd = (ev) => {
            const rect = this.progressBar.getBoundingClientRect();
            const clientX = ev.changedTouches ? ev.changedTouches[0].clientX : ev.clientX;
            let pct = (clientX - rect.left) / rect.width;
            pct = Math.max(0, Math.min(1, pct));

            const seekTime = pct * this._duration();
            if (this.isPlaying) this._startAt(seekTime);
            else this.startOffset = seekTime;

            this.isSeeking = false;
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onEnd);
            document.removeEventListener('touchmove', onMove);
            document.removeEventListener('touchend', onEnd);
        };

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onEnd);
        document.addEventListener('touchmove', onMove, { passive: false });
        document.addEventListener('touchend', onEnd);

        onMove(e);
    }

    // ─── LYRICS ─────────────────────────────────────────────────────────────

    updateLyricsHighlight(currentTime) {
        let newIndex = -1;
        for (let i = 0; i < this.lyrics.length; i++) {
            if (currentTime >= this.lyrics[i].time) {
                newIndex = i;
            } else {
                break;
            }
        }

        const lineChanged = newIndex !== this.currentLineIndex;
        if (lineChanged) {
            this.currentLineIndex = newIndex;
            this.highlightLines();
            this.scrollToActiveLine();
        }

        // Word-by-word highlight (runs every timeupdate)
        this.highlightWords(currentTime);
    }

    highlightLines() {
        const lines = this.lyricsScroll.querySelectorAll('.lyrics-line');

        lines.forEach((line, idx) => {
            line.classList.remove('active', 'past', 'upcoming');
            if (idx < this.currentLineIndex) {
                line.classList.add('past');
            } else if (idx === this.currentLineIndex) {
                line.classList.add('active');
            } else if (idx === this.currentLineIndex + 1) {
                line.classList.add('upcoming');
            }
        });
    }

    highlightWords(currentTime) {
        if (!this.wordTimings || this.currentLineIndex < 0) return;

        const words = this.lyricsScroll.querySelectorAll('.lyrics-word');
        words.forEach(wordEl => {
            const lineIdx = parseInt(wordEl.dataset.line);
            const wordIdx = parseInt(wordEl.dataset.word);
            const timings = this.wordTimings[lineIdx];

            if (!timings || !timings[wordIdx]) return;

            const { start, end } = timings[wordIdx];

            wordEl.classList.remove('word-active', 'word-past');

            if (lineIdx < this.currentLineIndex) {
                wordEl.classList.add('word-past');
            } else if (lineIdx === this.currentLineIndex) {
                if (currentTime >= start && currentTime < end) {
                    wordEl.classList.add('word-active');
                } else if (currentTime >= end) {
                    wordEl.classList.add('word-past');
                }
            }
        });
    }

    scrollToActiveLine() {
        const activeLine = this.lyricsScroll.querySelector('.lyrics-line.active');
        if (activeLine) {
            const sectionHeight = this.lyricsSection.clientHeight;
            const lineTop = activeLine.offsetTop;
            const lineHeight = activeLine.offsetHeight;
            const scrollTarget = lineTop - (sectionHeight / 2) + (lineHeight / 2);

            this.lyricsSection.scrollTo({
                top: scrollTarget,
                behavior: 'smooth'
            });
        }
    }

    // ─── HELPERS ────────────────────────────────────────────────────────────

    formatTime(sec) {
        if (isNaN(sec)) return '0:00';
        const m = Math.floor(sec / 60);
        const s = Math.floor(sec % 60);
        return `${m}:${s.toString().padStart(2, '0')}`;
    }
}

// Boot
document.addEventListener('DOMContentLoaded', () => {
    window.player = new KaraokePlayer();
});
