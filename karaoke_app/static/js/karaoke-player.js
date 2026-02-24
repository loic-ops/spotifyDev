/**
 * VoxPlayer - Lecteur avec mode karaoké
 * Utilise deux pistes audio (original + instrumental) avec fondu croisé.
 */

class KaraokePlayer {
    constructor() {
        // Audio elements
        this.audioOriginal = document.getElementById('audioOriginal');
        this.audioInstrumental = document.getElementById('audioInstrumental');

        // State
        this.songs = [];
        this.currentSong = null;
        this.lyrics = [];
        this.currentLineIndex = -1;
        this.isPlaying = false;
        this.karaokeLevel = 0; // 0=off, 1=léger, 2=moyen, 3=full
        this.karaokeMix = [
            { original: 1.0,  instrumental: 0.0  }, // Niveau 0 : voix originale
            { original: 0.65, instrumental: 0.5  }, // Niveau 1 : réduction légère
            { original: 0.30, instrumental: 0.85 }, // Niveau 2 : réduction moyenne
            { original: 0.05, instrumental: 1.0  }, // Niveau 3 : instrumental pur
        ];
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
        this.prevBtn = document.getElementById('prevBtn');
        this.nextBtn = document.getElementById('nextBtn');
        this.volumeSlider = document.getElementById('volumeSlider');
        this.karaokeToggle = document.getElementById('karaokeToggle');
        this.nowPlayingLabel = document.getElementById('nowPlayingLabel');
        this.backBtn = document.getElementById('backBtn');

        this.init();
    }

    init() {
        this.loadSongs();
        this.bindEvents();
        this.setVolume(80);
    }

    bindEvents() {
        // Back to song list
        this.backBtn.addEventListener('click', () => this.showSongList());

        // Playback
        this.playBtn.addEventListener('click', () => this.togglePlay());
        this.prevBtn.addEventListener('click', () => this.seekRelative(-10));
        this.nextBtn.addEventListener('click', () => this.seekRelative(10));

        // Volume
        this.volumeSlider.addEventListener('input', (e) => this.setVolume(e.target.value));

        // Karaoke toggle
        this.karaokeToggle.addEventListener('click', () => this.toggleKaraoke());

        // Progress bar seeking
        this.progressBar.addEventListener('mousedown', (e) => this.startSeek(e));
        this.progressBar.addEventListener('touchstart', (e) => this.startSeek(e), { passive: false });

        // Time update from original audio (master clock)
        this.audioOriginal.addEventListener('timeupdate', () => this.onTimeUpdate());
        this.audioOriginal.addEventListener('loadedmetadata', () => this.onMetadataLoaded());
        this.audioOriginal.addEventListener('ended', () => this.onEnded());
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
        if (!this.songs.length) {
            this.songList.innerHTML = `
                <div class="empty-library">
                    <i class="fas fa-music"></i>
                    <p>Aucune chanson disponible</p>
                    <a href="/admin/upload" class="btn-accent-sm">Ajouter une chanson</a>
                </div>`;
            return;
        }

        this.songList.innerHTML = this.songs.map((song, i) => `
            <div class="song-item" data-id="${song.id}">
                <div class="song-item-cover">
                    ${song.has_cover
                        ? `<img src="/api/cover/${song.id}" alt="">`
                        : `<div class="cover-placeholder"><i class="fas fa-music"></i></div>`}
                </div>
                <div class="song-item-info">
                    <span class="song-item-title">${song.title}</span>
                    <span class="song-item-artist">${song.artist || 'Artiste inconnu'}</span>
                </div>
                ${song.has_instrumental ? '<span class="karaoke-badge">K</span>' : ''}
            </div>
        `).join('');

        // Bind click events
        this.songList.querySelectorAll('.song-item').forEach(el => {
            el.addEventListener('click', () => this.selectSong(el.dataset.id));
        });
    }

    showSongList() {
        this.songListView.style.display = '';
        this.nowPlayingView.style.display = 'none';
        this.nowPlayingLabel.textContent = 'Choisir une chanson';
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
            this.coverArt.innerHTML = `<img src="/api/cover/${song.id}" alt="${song.title}">`;
        } else {
            this.coverArt.innerHTML = '<i class="fas fa-music"></i>';
        }

        // Dynamic background gradient based on song
        this.updateBackground(song);

        // Load audio sources
        this.audioOriginal.src = `/api/audio/${song.id}/original`;
        this.audioOriginal.load();

        if (song.has_instrumental) {
            this.audioInstrumental.src = `/api/audio/${song.id}/instrumental`;
            this.audioInstrumental.load();
            this.karaokeToggle.classList.remove('disabled');
        } else {
            this.audioInstrumental.src = '';
            this.karaokeToggle.classList.add('disabled');
            this.karaokeLevel = 0;
            this.updateKaraokeUI();
        }

        // Load lyrics
        await this.loadLyrics(song.id);

        // Show player
        this.songListView.style.display = 'none';
        this.nowPlayingView.style.display = '';

        // Reset state
        this.isPlaying = false;
        this.currentLineIndex = -1;
        this.updatePlayIcon();
        this.updateKaraokeAudioLevels();
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
        // Keep spacers, replace content between them
        const spacerTop = '<div class="lyrics-spacer"></div>';
        const spacerBottom = '<div class="lyrics-spacer"></div>';

        if (!this.lyrics.length) {
            this.lyricsScroll.innerHTML = spacerTop +
                '<p class="lyrics-line lyrics-placeholder">Pas de paroles disponibles</p>' +
                spacerBottom;
            return;
        }

        const linesHtml = this.lyrics.map((line, i) =>
            `<p class="lyrics-line" data-index="${i}">${line.text}</p>`
        ).join('');

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
        this.audioOriginal.play();
        if (this.karaokeLevel > 0 && this.audioInstrumental.src) {
            this.audioInstrumental.currentTime = this.audioOriginal.currentTime;
            this.audioInstrumental.play();
        }
        this.isPlaying = true;
        this.updatePlayIcon();
    }

    pause() {
        this.audioOriginal.pause();
        this.audioInstrumental.pause();
        this.isPlaying = false;
        this.updatePlayIcon();
    }

    updatePlayIcon() {
        this.playIcon.className = this.isPlaying ? 'fas fa-pause' : 'fas fa-play';
    }

    seekRelative(seconds) {
        const newTime = Math.max(0, Math.min(
            this.audioOriginal.duration || 0,
            this.audioOriginal.currentTime + seconds
        ));
        this.audioOriginal.currentTime = newTime;
        if (this.audioInstrumental.src) {
            this.audioInstrumental.currentTime = newTime;
        }
    }

    setVolume(val) {
        const v = val / 100;
        this.audioOriginal.volume = v;
        this.audioInstrumental.volume = v;
        this.updateKaraokeAudioLevels();
    }

    onMetadataLoaded() {
        this.totalTimeEl.textContent = this.formatTime(this.audioOriginal.duration);
    }

    onTimeUpdate() {
        if (this.isSeeking) return;

        const current = this.audioOriginal.currentTime;
        const duration = this.audioOriginal.duration || 1;
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
        // Play next song if available
        if (this.currentSong) {
            const idx = this.songs.findIndex(s => s.id === this.currentSong.id);
            if (idx < this.songs.length - 1) {
                this.selectSong(this.songs[idx + 1].id);
                setTimeout(() => this.play(), 500);
            }
        }
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
            this.currentTimeEl.textContent = this.formatTime(pct * (this.audioOriginal.duration || 0));
        };

        const onEnd = (ev) => {
            const rect = this.progressBar.getBoundingClientRect();
            const clientX = ev.changedTouches ? ev.changedTouches[0].clientX : ev.clientX;
            let pct = (clientX - rect.left) / rect.width;
            pct = Math.max(0, Math.min(1, pct));

            const seekTime = pct * (this.audioOriginal.duration || 0);
            this.audioOriginal.currentTime = seekTime;
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

    // ─── RÉDUCTION VOCALE (multi-niveaux) ──────────────────────────────────

    toggleKaraoke() {
        if (!this.currentSong?.has_instrumental) return;

        // Cycle : 0 → 1 → 2 → 3 → 0
        this.karaokeLevel = (this.karaokeLevel + 1) % this.karaokeMix.length;

        this.updateKaraokeUI();

        if (this.karaokeLevel > 0 && this.isPlaying) {
            this.audioInstrumental.currentTime = this.audioOriginal.currentTime;
            this.audioInstrumental.play();
        } else if (this.karaokeLevel === 0) {
            this.audioInstrumental.pause();
        }

        this.updateKaraokeAudioLevels();
    }

    updateKaraokeUI() {
        const btn = this.karaokeToggle;
        const badge = document.getElementById('karaokeLevelBadge');

        btn.classList.toggle('active', this.karaokeLevel > 0);
        btn.dataset.level = this.karaokeLevel;

        if (this.karaokeLevel > 0) {
            badge.textContent = this.karaokeLevel;
            badge.style.display = '';
        } else {
            badge.textContent = '';
            badge.style.display = 'none';
        }
    }

    updateKaraokeAudioLevels() {
        const baseVolume = this.volumeSlider.value / 100;
        const mix = this.karaokeMix[this.karaokeLevel];

        this.audioOriginal.volume = baseVolume * mix.original;
        this.audioInstrumental.volume = baseVolume * mix.instrumental;
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

        if (newIndex !== this.currentLineIndex) {
            this.currentLineIndex = newIndex;
            this.highlightAndScroll();
        }
    }

    highlightAndScroll() {
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

        // Smooth scroll to center the active line
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
