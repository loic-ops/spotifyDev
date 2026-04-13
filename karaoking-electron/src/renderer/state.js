// state global de l'app
// persist localStorage: favoris, recherches, queue
// reactive via Proxy pour maj des views

export class AppState {
  constructor() {
    this.songs = [];
    this.currentSong = null;
    this.queue = [];
    this.favorites = new Set();
    this.recentSearches = [];
    this.settings = {
      bgMode: 'dynamic',
      masterVolume: 1.0,
      venueId: null
    };

    this.load();
    this.saveDebounced = this._debounce(this.save.bind(this), 500);
  }

  load() {
    try {
      const raw = JSON.parse(localStorage.getItem('karaoking-state') || '{}');
      this.favorites = new Set(raw.favorites || []);
      this.recentSearches = raw.recentSearches?.slice(-10) || [];
      this.settings = { ...this.settings, ...raw.settings };
      this.queue = raw.queue || [];
    } catch {}
  }

  save() {
    localStorage.setItem('karaoking-state', JSON.stringify({
      favorites: Array.from(this.favorites),
      recentSearches: this.recentSearches,
      settings: this.settings,
      queue: this.queue
    }));
  }

  _debounce(fn, ms) {
    let tid;
    return (...args) => {
      clearTimeout(tid);
      tid = setTimeout(() => fn(...args), ms);
    };
  }

  toggleFavorite(songId) {
    if (this.favorites.has(songId)) this.favorites.delete(songId);
    else this.favorites.add(songId);
    this.saveDebounced();
  }

  isFavorite(songId) { return this.favorites.has(songId); }

  addRecentSearch(term) {
    this.recentSearches = [term, ...this.recentSearches.filter(s => s !== term)].slice(0, 10);
    this.saveDebounced();
  }

  addToQueue(songId, atFront = false) {
    const song = this.songs.find(s => s.id === songId);
    if (!song) return;
    const data = { id: song.id, title: song.title, artist: song.artist };
    atFront ? this.queue.unshift(data) : this.queue.push(data);
    this.saveDebounced();
  }

  // proxy reactif
  static create(songs) {
    const st = new AppState();
    st.songs = songs;
    return new Proxy(st, {
      set(target, prop, value) {
        target[prop] = value;
        target.saveDebounced();
        document.dispatchEvent(new CustomEvent('statechange', { detail: { prop, value } }));
        return true;
      }
    });
  }
}

// singleton — init apres loadSongs
let state;
export const initState = (songs) => {
  state = AppState.create(songs);
  return state;
};
export default () => state;
