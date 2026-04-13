// skeletons liquid glass — no spinners
export function renderSkeleton(type, count = 1) {
  let out = '';
  for (let i = 0; i < count; i++) {
    if (type === 'song-card') {
      out += `
        <div class="song-card glass-card">
          <div class="song-card-cover skeleton-cover"></div>
          <div class="skeleton-line"></div>
          <div class="skeleton-line skeleton-line-sm"></div>
        </div>`;
    } else if (type === 'song-row') {
      out += `
        <div class="song-row glass">
          <div class="sr-cover skeleton" style="width:44px;height:44px;border-radius:8px;"></div>
          <div style="flex:1;">
            <div class="skeleton-line" style="width:70%;height:14px;"></div>
            <div class="skeleton-line skeleton-line-sm" style="width:50%;height:12px;margin-top:2px;"></div>
          </div>
        </div>`;
    } else if (type === 'artist-card') {
      out += `
        <div class="artist-card glass-card">
          <div class="artist-avatar skeleton" style="width:120px;height:120px;border-radius:50%;"></div>
          <div class="skeleton-line" style="width:80%;height:12px;margin:8px auto;"></div>
          <div class="skeleton-line skeleton-line-sm" style="width:40%;height:10px;margin:0 auto;"></div>
        </div>`;
    } else if (type === 'carousel') {
      // TODO: rendre le nombre de cards dynamique selon la largeur
      out += `
        <div class="h-scroll">
          ${Array(6).fill().map(() => renderSkeleton('song-card')).join('')}
        </div>`;
    }
  }
  return out;
}
