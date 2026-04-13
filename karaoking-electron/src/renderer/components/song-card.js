// carte chanson reutilisable — home/discover/library/search

export function renderSongCard(song, opts = {}) {
  const {
    showFavorite = false,
    showQueue = false,
    isPlaying = false,
    compact = false,
    skeleton = false
  } = opts;

  if (skeleton) {
    return `
      <div class="song-card glass-card">
        <div class="song-card-cover skeleton skeleton-cover"></div>
        <div class="skeleton-line"></div>
        <div class="skeleton-line sm"></div>
      </div>`;
  }

  const cover = window.karaoking.getCoverUrl(song.id);
  const karaokeReady = song.has_instrumental && song.has_lyrics;
  const fav = state.isFavorite(song.id);

  let html = `
    <div class="song-card glass-card ${isPlaying ? 'playing' : ''}" data-id="${song.id}">
      <div class="song-card-cover" style="background-image: url(${cover})">
        <div class="cover-ph" style="display: ${song.has_cover ? 'none' : 'flex'}">
          <i class="fas fa-music"></i>
        </div>
        <button class="card-play-btn" onclick="playSong('${song.id}')">
          <i class="fas fa-play"></i>
        </button>
  `;

  if (showFavorite) {
    html += `
        <button class="card-fav-btn ${fav ? 'active' : ''}" onclick="state.toggleFavorite('${song.id}'); this.classList.toggle('active')">
          <i class="fas fa-star"></i>
        </button>`;
  }

  if (showQueue) {
    html += `
        <button class="card-queue-btn" onclick="state.addToQueue('${song.id}');" title="Ajouter à la queue">
          <i class="fas fa-plus"></i>
        </button>`;
  }

  html += `
      </div>
      <div class="song-card-title">${song.title}</div>
      <div class="song-card-artist">${song.artist || 'Artiste inconnu'}</div>`;

  if (karaokeReady && !compact) {
    html += '<span class="sr-badge glass">Karaoké</span>';
  }

  html += '</div>';
  return html;
}

// helper global pour onclick inline
window.playSong = (songId) => {
  // console.log('playSong called:', songId);
  const song = state.songs.find(s => s.id === songId);
  if (song) playSong(songId);
};
