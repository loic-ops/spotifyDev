/**
 * KaraoKing - Lecteur avec mode karaoké
 * Utilise deux pistes audio (original + instrumental) avec fondu croisé.
 */

class KaraokePlayer {
    constructor() {
        // Audio elements (deux pistes séparées : voix + instrumental)
        this.audioVocals = document.getElementById('audioVocals');
        this.audioInstrumental = document.getElementById('audioInstrumental');

        // State
        this.songs = [];
        this.currentSong = null;
        this.lyrics = [];
        this.currentLineIndex = -1;
        this.isPlaying = false;
        this.isSeeking = false;

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
            // Auto-play if ?play=songId in URL (from library page)
            const params = new URLSearchParams(window.location.search);
            const playId = params.get('play');
            if (playId && this.songs.find(s => s.id === playId)) {
                this.selectSong(playId);
                setTimeout(() => this.play(), 500);
                // Clean URL
                window.history.replaceState({}, '', '/');
            }
        });
        this.bindEvents();
        this.audioVocals.volume = 1;
        this.audioInstrumental.volume = 1;
    }

    /** Escape HTML to prevent XSS */
    _esc(str) {
        if (!str) return '';
        return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
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

        // Track sliders (voix + instrumental)
        this.vocalsSlider.addEventListener('input', (e) => { this.audioVocals.volume = e.target.value / 100; });
        this.instrumentalSlider.addEventListener('input', (e) => { this.audioInstrumental.volume = e.target.value / 100; });

        // Progress bar seeking
        this.progressBar.addEventListener('mousedown', (e) => this.startSeek(e));
        this.progressBar.addEventListener('touchstart', (e) => this.startSeek(e), { passive: false });

        // Time update from vocals track (master clock)
        this.audioVocals.addEventListener('timeupdate', () => this.onTimeUpdate());
        this.audioVocals.addEventListener('loadedmetadata', () => this.onMetadataLoaded());
        this.audioVocals.addEventListener('ended', () => this.onEnded());
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

        if (!hasSongs) {
            this.songList.innerHTML = `
                <div class="empty-library">
                    <div class="empty-icon-wrap">
                        <i class="fas fa-record-vinyl"></i>
                    </div>
                    <h3>Aucune chanson disponible</h3>
                    <p>Importez vos premieres chansons depuis l'interface admin</p>
                </div>`;
            if (searchWrap) searchWrap.style.display = 'none';
            if (statsBar) statsBar.style.display = 'none';
            if (karaokeSection) karaokeSection.style.display = 'none';
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

        input.addEventListener('input', () => {
            const q = input.value.toLowerCase().trim();
            if (clearBtn) clearBtn.style.display = q ? '' : 'none';

            // Filter all songs grid
            this.songList.querySelectorAll('.song-grid-item').forEach(el => {
                const id = el.dataset.id;
                const song = this.songs.find(s => s.id === id);
                if (!song) return;
                const match = !q || song.title.toLowerCase().includes(q) || (song.artist || '').toLowerCase().includes(q);
                el.style.display = match ? '' : 'none';
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
        });

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                input.value = '';
                input.dispatchEvent(new Event('input'));
                input.focus();
            });
        }
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

        this.currentSong = song;

        // Update UI
        this.songTitle.textContent = song.title;
        this.songArtist.textContent = song.artist || 'Artiste inconnu';
        this.nowPlayingLabel.textContent = song.title;

        // Cover art
        if (song.has_cover) {
            this.coverArt.innerHTML = `<img src="/api/cover/${this._esc(song.id)}" alt="${this._esc(song.title)}">`;
        } else {
            this.coverArt.innerHTML = '<i class="fas fa-music"></i>';
        }

        // Dynamic background gradient based on song
        this.updateBackground(song);

        // Load audio sources (vocals + instrumental séparés)
        if (song.has_vocals && song.has_instrumental) {
            this.audioVocals.src = `/api/audio/${song.id}/vocals`;
            this.audioInstrumental.src = `/api/audio/${song.id}/instrumental`;
            this.audioVocals.load();
            this.audioInstrumental.load();
            this.trackSlidersContainer.classList.remove('disabled');
        } else {
            // Fallback: jouer l'original sur la piste vocals
            this.audioVocals.src = `/api/audio/${song.id}/original`;
            this.audioVocals.load();
            this.audioInstrumental.src = '';
            this.trackSlidersContainer.classList.add('disabled');
        }

        // Load lyrics
        await this.loadLyrics(song.id);

        // Show player
        this.songListView.style.display = 'none';
        this.nowPlayingView.style.display = '';

        // Highlight in list
        this._updateListHighlight();

        // Reset state
        this.isPlaying = false;
        this.currentLineIndex = -1;
        this.updatePlayIcon();
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

    togglePlay() {
        if (this.isPlaying) {
            this.pause();
        } else {
            this.play();
        }
    }

    play() {
        this.audioVocals.play();
        if (this.audioInstrumental.src) {
            this.audioInstrumental.currentTime = this.audioVocals.currentTime;
            this.audioInstrumental.play();
        }
        this.isPlaying = true;
        this.updatePlayIcon();
    }

    pause() {
        this.audioVocals.pause();
        this.audioInstrumental.pause();
        this.isPlaying = false;
        this.updatePlayIcon();
    }

    updatePlayIcon() {
        this.playIcon.className = this.isPlaying ? 'fas fa-pause' : 'fas fa-play';
    }

    seekRelative(seconds) {
        const newTime = Math.max(0, Math.min(
            this.audioVocals.duration || 0,
            this.audioVocals.currentTime + seconds
        ));
        this.audioVocals.currentTime = newTime;
        if (this.audioInstrumental.src) {
            this.audioInstrumental.currentTime = newTime;
        }
    }

    setVolume(val) {
        const v = val / 100;
        this.audioVocals.volume = v * (this.vocalsSlider.value / 100);
        this.audioInstrumental.volume = v * (this.instrumentalSlider.value / 100);
    }

    onMetadataLoaded() {
        this.totalTimeEl.textContent = this.formatTime(this.audioVocals.duration);
    }

    onTimeUpdate() {
        if (this.isSeeking) return;

        const current = this.audioVocals.currentTime;
        const duration = this.audioVocals.duration || 1;
        const pct = (current / duration) * 100;

        this.progressPlayed.style.width = pct + '%';
        this.progressThumb.style.left = pct + '%';
        this.currentTimeEl.textContent = this.formatTime(current);

        this.updateLyricsHighlight(current);
    }

    onEnded() {
        this.isPlaying = false;
        this.updatePlayIcon();
        this.audioInstrumental.pause();
        this.nextSong(true);
    }

    nextSong(autoPlay = false) {
        if (!this.currentSong) return;
        const idx = this.songs.findIndex(s => s.id === this.currentSong.id);
        if (idx < this.songs.length - 1) {
            this.selectSong(this.songs[idx + 1].id);
            if (autoPlay) setTimeout(() => this.play(), 500);
        }
    }

    prevSong() {
        if (!this.currentSong) return;
        // If more than 3 seconds in, restart the song
        if (this.audioVocals.currentTime > 3) {
            this.audioVocals.currentTime = 0;
            if (this.audioInstrumental.src) this.audioInstrumental.currentTime = 0;
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
        this.isSeeking = true;

        const onMove = (ev) => {
            const rect = this.progressBar.getBoundingClientRect();
            const clientX = ev.touches ? ev.touches[0].clientX : ev.clientX;
            let pct = (clientX - rect.left) / rect.width;
            pct = Math.max(0, Math.min(1, pct));

            this.progressPlayed.style.width = (pct * 100) + '%';
            this.progressThumb.style.left = (pct * 100) + '%';
            this.currentTimeEl.textContent = this.formatTime(pct * (this.audioVocals.duration || 0));
        };

        const onEnd = (ev) => {
            const rect = this.progressBar.getBoundingClientRect();
            const clientX = ev.changedTouches ? ev.changedTouches[0].clientX : ev.clientX;
            let pct = (clientX - rect.left) / rect.width;
            pct = Math.max(0, Math.min(1, pct));

            const seekTime = pct * (this.audioVocals.duration || 0);
            this.audioVocals.currentTime = seekTime;
            if (this.audioInstrumental.src) {
                this.audioInstrumental.currentTime = seekTime;
            }

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
