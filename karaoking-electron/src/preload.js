const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('karaoking', {
    // Server
    connectServer: (url) => ipcRenderer.invoke('server:connect', url),
    getSavedServer: () => ipcRenderer.invoke('server:getSaved'),
    getServerUrl: () => ipcRenderer.invoke('api:serverUrl'),

    // API
    fetchApi: (endpoint) => ipcRenderer.invoke('api:fetch', endpoint),
    getAudioUrl: (songId, trackType) => ipcRenderer.invoke('api:audioUrl', songId, trackType),
    getCoverUrl: (songId) => ipcRenderer.invoke('api:coverUrl', songId),

    // Navigation
    goto: (page) => ipcRenderer.invoke('nav:goto', page),
    goConnect: () => ipcRenderer.invoke('nav:connect'),
});
