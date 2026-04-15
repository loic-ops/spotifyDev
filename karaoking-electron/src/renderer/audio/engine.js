// audio engine — dual track sync avec Web Audio API
// prepare pour SoundTouchJS pitch/tempo (M5)

export class AudioEngine {
  constructor() {
    this.audioCtx = null;
    this.bufV = null;   // vocals ou original
    this.bufI = null;   // instrumental
    this.srcV = null;
    this.srcI = null;
    this.gainV = null;
    this.gainI = null;
    this.gainMaster = null;
    this.startCtxTime = 0;
    this.startOffset = 0;
    this.hasI = false;
    this.isPlaying = false;
    this.isSeeking = false;
    this.playbackRate = 1.0;
    this.callbacks = { timeupdate: [], ended: [], error: [] };
  }

  async init() {
    if (this.audioCtx) return;
    this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    this.gainV = this.audioCtx.createGain();
    this.gainI = this.audioCtx.createGain();
    this.gainMaster = this.audioCtx.createGain();
    this.gainV.connect(this.gainMaster);
    this.gainI.connect(this.gainMaster);
    this.gainMaster.connect(this.audioCtx.destination);
    this.setVocalsGain(1.0);
    this.setInstrumentalGain(1.0);
  }

  getDuration() { return this.bufV ? this.bufV.duration : 0; }

  getCurrentTime() {
    if (!this.bufV) return 0;
    if (this.isPlaying) {
      const elapsed = (this.audioCtx.currentTime - this.startCtxTime) * this.playbackRate;
      return Math.min(this.getDuration(), this.startOffset + elapsed);
    }
    return this.startOffset;
  }

  stopSources() {
    [this.srcV, this.srcI].forEach(s => {
      if (!s) return;
      try { s.onended = null; s.stop(); } catch {}
      try { s.disconnect(); } catch {}
    });
    this.srcV = null;
    this.srcI = null;
  }

  async startAt(offset = 0) {
    await this.init();
    this.stopSources();
    if (!this.bufV) return;

    const when = this.audioCtx.currentTime + 0.05;

    // source vocals/original
    this.srcV = this.audioCtx.createBufferSource();
    this.srcV.buffer = this.bufV;
    this.srcV.connect(this.gainV);
    this.srcV.onended = () => {
      if (!this.isPlaying) return;
      if (this.getCurrentTime() >= this.getDuration() - 0.1) {
        this.isPlaying = false;
        this.callbacks.ended.forEach(cb => cb());
      }
    };

    // instru si dispo
    if (this.hasI && this.bufI) {
      this.srcI = this.audioCtx.createBufferSource();
      this.srcI.buffer = this.bufI;
      this.srcI.connect(this.gainI);
    }

    this.srcV.playbackRate.value = this.playbackRate;
    if (this.srcI) this.srcI.playbackRate.value = this.playbackRate;

    this.srcV.start(when, offset);
    if (this.srcI) this.srcI.start(when, offset);

    this.startCtxTime = when;
    this.startOffset = offset;
    this.isPlaying = true;

    if (this.audioCtx.state === 'suspended') {
      try { await this.audioCtx.resume(); } catch {}
    }
  }

  async load(songId, songData) {
    this.stopSources();
    this.bufV = null;
    this.bufI = null;
    this.hasI = false;
    this.startOffset = 0;
    this.isPlaying = false;

    try {
      if (songData.has_vocals && songData.has_instrumental) {
        const [vUrl, iUrl] = await Promise.all([
          window.karaoking.getAudioUrl(songId, 'vocals'),
          window.karaoking.getAudioUrl(songId, 'instrumental')
        ]);
        // FIXME: gerer le cas ou un seul buffer fail
        const [vBuf, iBuf] = await Promise.all([
          this.fetchBuffer(vUrl),
          this.fetchBuffer(iUrl)
        ]);
        this.bufV = vBuf;
        this.bufI = iBuf;
        this.hasI = true;
      } else {
        const url = await window.karaoking.getAudioUrl(songId, 'original');
        this.bufV = await this.fetchBuffer(url);
      }
    } catch (e) {
      this.callbacks.error.forEach(cb => cb(e));
      throw e;
    }
  }

  async fetchBuffer(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const arr = await resp.arrayBuffer();
    return await this.audioCtx.decodeAudioData(arr);
  }

  play() {
    if (this.bufV) this.startAt(this.startOffset);
  }

  pause() {
    const pos = this.getCurrentTime();
    this.stopSources();
    this.startOffset = pos;
    this.isPlaying = false;
  }

  seek(time) {
    this.startOffset = Math.max(0, Math.min(this.getDuration(), time));
    if (this.isPlaying) this.startAt(this.startOffset);
  }

  setVocalsGain(val) {
    if (this.gainV) this.gainV.gain.value = val;
  }

  setInstrumentalGain(val) {
    if (this.gainI) this.gainI.gain.value = val;
  }

  setPlaybackRate(rate) {
    // Checkpointer la position avant de changer le rate
    // sinon getCurrentTime() recalcule tout l'elapsed avec le nouveau rate
    if (this.isPlaying && this.audioCtx) {
      const now = this.audioCtx.currentTime;
      const elapsed = (now - this.startCtxTime) * this.playbackRate;
      this.startOffset = Math.min(this.getDuration(), this.startOffset + elapsed);
      this.startCtxTime = now;
    }
    this.playbackRate = rate;
    if (this.srcV) this.srcV.playbackRate.value = rate;
    if (this.srcI) this.srcI.playbackRate.value = rate;
  }

  on(event, callback) {
    if (this.callbacks[event]) this.callbacks[event].push(callback);
  }

  // boucle rAF pour UI — pas de timeupdate natif sur AudioBufferSource
  startTick(cb) {
    const tick = () => {
      if (!this.isSeeking && this.bufV) {
        cb(this.getCurrentTime(), this.getDuration(), this.isPlaying);
      }
      requestAnimationFrame(tick);
    };
    tick();
  }
}

// singleton
const engine = new AudioEngine();
export default engine;
