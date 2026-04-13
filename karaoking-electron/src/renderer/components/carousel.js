// carousel horizontal — auto-advance + indicators

export function renderCarousel(songs, title = 'À découvrir') {
  if (!songs?.length) {
    return `
      <div class="section-header">
        <div class="section-title">${title}</div>
      </div>
      <div class="empty-state">
        <i class="fas fa-star"></i>
        <p>Aucun contenu disponible</p>
      </div>`;
  }

  const slug = title.toLowerCase().replace(/\\s+/g, '-');
  const id = `carousel-${slug}`;

  const html = `
    <div class="section-header">
      <div class="section-title">${title}</div>
      <button class="section-link" onclick="navigate('library')">Voir tout</button>
    </div>
    <div class="h-scroll carousel" data-carousel="${slug}" id="${id}">
      ${songs.map(song => renderSongCard(song, { compact: true })).join('')}
    </div>`;

  // init apres que le DOM soit pret
  requestAnimationFrame(() => initCarousel(`#${id}`));

  return html;
}

function initCarousel(selector) {
  const el = document.querySelector(selector);
  if (!el) return;

  const scrollLeft = () => el.scrollBy({ left: -el.clientWidth + 32, behavior: 'smooth' });
  const scrollRight = () => el.scrollBy({ left: el.clientWidth - 32, behavior: 'smooth' });

  // dots indicateurs
  const dots = document.createElement('div');
  dots.className = 'carousel-indicators';
  el.parentNode.appendChild(dots);

  let curPage = 0;
  const pageCount = Math.ceil(el.scrollWidth / el.clientWidth);

  function updateDots() {
    curPage = Math.round(el.scrollLeft / el.clientWidth);
    dots.innerHTML = `
      <span class="indicator-dot active" style="--i: ${curPage}"></span>
      ${Array(pageCount - 1).fill().map((_, i) =>
        `<span class="indicator-dot" style="--i: ${i + 1}"></span>`
      ).join('')}`;
  }

  el.addEventListener('scroll', updateDots);
  updateDots();

  // auto-advance toutes les 4s
  let timer;
  const startAuto = () => {
    timer = setInterval(() => {
      if (el.scrollLeft >= el.scrollWidth - el.clientWidth - 1) {
        el.scrollTo({ left: 0, behavior: 'smooth' });
      } else {
        scrollRight();
      }
    }, 4000);
  };

  el.onmouseenter = () => clearInterval(timer);
  el.onmouseleave = startAuto;
  startAuto();

  // clavier
  el.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft') scrollLeft();
    if (e.key === 'ArrowRight') scrollRight();
  });
  el.tabIndex = 0;
}

// inject carousel styles une seule fois
if (!document.querySelector('#carousel-styles')) {
  const s = document.createElement('style');
  s.id = 'carousel-styles';
  s.textContent = `
    .carousel-indicators {
      display: flex; gap: 6px; justify-content: center;
      margin-top: 12px; padding: 8px;
    }
    .indicator-dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--glass); cursor: pointer;
      transition: background var(--dur-fast);
    }
    .indicator-dot.active {
      background: var(--accent);
      box-shadow: 0 0 12px var(--accent-glow);
    }
    .carousel:hover .indicator-dot:hover { background: var(--accent-soft); }
  `;
  document.head.appendChild(s);
}
