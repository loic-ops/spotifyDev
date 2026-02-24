// Karaoke Player JavaScript

class KaraokePlayer {
    constructor() {
        // DOM Elements
        this.songSelect = document.getElementById('songSelect');
        this.playerSection = document.getElementById('playerSection');
        this.currentSongTitle = document.getElementById('currentSongTitle');
        this.songStatus = document.getElementById('songStatus');
        this.lyricsContent = document.getElementById('lyricsContent');
        this.audioPlayer = document.getElementById('audioPlayer');
        this.trackType = document.getElementById('trackType');
        this.vocalReduction = document.getElementById('vocalReduction');
        this.vocalLevel = document.getElementById('vocalLevel');
        this.progressBar = document.getElementById('progressBar');
        this.progressFill = document.getElementById('progressFill');
        this.progressHandle = document.getElementById('progressHandle');
        this.currentTimeEl = document.getElementById('currentTime');
        this.totalTimeEl = document.getElementById('totalTime');
        this.playBtn = document.getElementById('playBtn');
        this.prevBtn = document.getElementById('prevBtn');
        this.nextBtn = document.getElementById('nextBtn');
        this.volumeSlider = document.getElementById('volumeSlider');
        this.volumeLevel = document.getElementById('volumeLevel');

        // State
        this.currentSong = null;
        this.lyrics = [];
        this.currentLineIndex = -1;
        this.isPlaying = false;
        
        // Initialize
        this.init();
    }

    init() {
        this.loadSongs();
        this.bindEvents();
    }

    bindEvents() {
        // Song selection
        this.songSelect.addEventListener('change', (e) => this.selectSong(e.target.value));
        
        // Track type change
        this.trackType.addEventListener('change', () => this.changeTrack());
        
        // Vocal reduction
        this.vocalReduction.addEventListener('input', (e) => {
            this.vocalLevel.textContent = `${e.target.value}%`;
        });
        
        // Play/Pause
        this.playBtn.addEventListener('click', () => this.togglePlay());
        
        // Previous/Next
        this.prevBtn.addEventListener('click', () => this.prevLine());
        this.nextBtn.addEventListener('click', () => this.nextLine());
        
        // Volume
        this.volumeSlider.addEventListener('input', (e) => this.setVolume(e.target.value));
        
        // Progress bar click
        this.progressBar.addEventListener('click', (e) => this.seek(e));
        
        // Audio time update
        this.audioPlayer.addEventListener('timeupdate', () => this.updateProgress());
        
        // Audio ended
        this.audioPlayer.addEventListener('ended', () => this.onSongEnd());
        
        // Audio loaded
        this.audioPlayer.addEventListener('loadedmetadata', () => this.onMetadataLoaded());
    }

    async loadSongs() {
        try {
            const response = await fetch('/api/songs');
            const songs = await response.json();
            
            this.songSelect.innerHTML = '<option value="">-- Choose a song --</option>';
            
            songs.forEach(song => {
                const option = document.createElement('option');
                option.value = song.id;
                option.textContent = song.title;
                this.songSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading songs:', error);
        }
    }

    async selectSong(songId) {
        if (!songId) {
            this.playerSection.style.display = 'none';
            return;
        }

        this.currentSong = songId;
        this.playerSection.style.display = 'block';
        
        // Get song info
        const songs = await fetch('/api/songs').then(r => r.json());
        const song = songs.find(s => s.id === songId);
        
        this.currentSongTitle.textContent = song ? song.title : 'Unknown';
        this.songStatus.textContent = 'Loading lyrics...';
        
        // Load lyrics
        await this.loadLyrics(songId);
        
        // Load audio
        this.changeTrack();
    }

    async loadLyrics(songId) {
        try {
            const response = await fetch(`/api/lyrics/${songId}`);
            
            if (!response.ok) {
                throw new Error('No lyrics available');
            }
            
            const data = await response.json();
            this.lyrics = data.segments;
            
            this.renderLyrics();
            this.songStatus.textContent = 'Ready to play';
            
            // Auto-scroll to middle
            this.scrollToCurrentLine();
            
        } catch (error) {
            console.error('Error loading lyrics:', error);
            this.lyrics = [];
            this.renderLyrics();
            this.songStatus.textContent = 'No lyrics available';
        }
    }

    renderLyrics() {
        this.lyricsContent.innerHTML = '';
        
        if (this.lyrics.length === 0) {
            this.lyricsContent.innerHTML = '<p class="placeholder">No lyrics available</p>';
            return;
        }
        
        this.lyrics.forEach((line, index) => {
            const p = document.createElement('p');
            p.textContent = line.text;
            p.dataset.index = index;
            this.lyricsContent.appendChild(p);
        });
    }

    changeTrack() {
        if (!this.currentSong) return;
        
        const trackType = this.trackType.value;
        const audioSrc = `/api/audio/${this.currentSong}/${trackType}`;
        
        this.audioPlayer.src = audioSrc;
        this.audioPlayer.load();
        
        this.songStatus.textContent = `Playing: ${this.getTrackName(trackType)}`;
    }

    getTrackName(type) {
        const names = {
            'karaoke': 'Karaoke (Reduced Vocals)',
            'instrumental': 'Instrumental Only',
            'original': 'Original (With Vocals)'
        };
        return names[type] || type;
    }

    togglePlay() {
        if (this.isPlaying) {
            this.pause();
        } else {
            this.play();
        }
    }

    play() {
        this.audioPlayer.play();
        this.isPlaying = true;
        this.playBtn.innerHTML = '<i class="fas fa-pause"></i>';
        this.songStatus.textContent = 'Playing...';
    }

    pause() {
        this.audioPlayer.pause();
        this.isPlaying = false;
        this.playBtn.innerHTML = '<i class="fas fa-play"></i>';
        this.songStatus.textContent = 'Paused';
    }

    updateProgress() {
        const currentTime = this.audioPlayer.currentTime;
        const duration = this.audioPlayer.duration || 1;
        
        // Update progress bar
        const percentage = (currentTime / duration) * 100;
        this.progressFill.style.width = `${percentage}%`;
        this.progressHandle.style.left = `${percentage}%`;
        
        // Update time display
        this.currentTimeEl.textContent = this.formatTime(currentTime);
        
        // Update lyrics highlight
        this.updateLyricsHighlight(currentTime);
    }

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
            this.highlightCurrentLine();
        }
    }

    highlightCurrentLine() {
        const lines = this.lyricsContent.querySelectorAll('p');
        
        lines.forEach((line, index) => {
            line.classList.remove('active', 'past');
            
            if (index < this.currentLineIndex) {
                line.classList.add('past');
            } else if (index === this.currentLineIndex) {
                line.classList.add('active');
            }
        });
        
        this.scrollToCurrentLine();
    }

    scrollToCurrentLine() {
        const activeLine = this.lyricsContent.querySelector('.active');
        
        if (activeLine) {
            const container = document.getElementById('lyricsDisplay');
            const containerHeight = container.clientHeight;
            const lineTop = activeLine.offsetTop;
            const lineHeight = activeLine.clientHeight;
            
            // Scroll to center the active line
            const scrollTo = lineTop - (containerHeight / 2) + (lineHeight / 2);
            
            this.lyricsContent.style.transform = `translateY(-${scrollTo}px)`;
        }
    }

    seek(e) {
        const rect = this.progressBar.getBoundingClientRect();
        const percentage = (e.clientX - rect.left) / rect.width;
        const seekTime = percentage * this.audioPlayer.duration;
        
        this.audioPlayer.currentTime = seekTime;
    }

    prevLine() {
        if (this.currentLineIndex > 0) {
            const prevLine = this.lyrics[this.currentLineIndex - 1];
            this.audioPlayer.currentTime = prevLine.time;
        }
    }

    nextLine() {
        if (this.currentLineIndex < this.lyrics.length - 1) {
            const nextLine = this.lyrics[this.currentLineIndex + 1];
            this.audioPlayer.currentTime = nextLine.time;
        }
    }

    setVolume(value) {
        const volume = value / 100;
        this.audioPlayer.volume = volume;
        this.volumeLevel.textContent = `${value}%`;
    }

    onMetadataLoaded() {
        this.totalTimeEl.textContent = this.formatTime(this.audioPlayer.duration);
    }

    onSongEnd() {
        this.isPlaying = false;
        this.playBtn.innerHTML = '<i class="fas fa-play"></i>';
        this.songStatus.textContent = 'Song ended';
        
        // Reset lyrics
        this.currentLineIndex = -1;
        this.highlightCurrentLine();
    }

    formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
}

// Initialize player when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.karaokePlayer = new KaraokePlayer();
});

