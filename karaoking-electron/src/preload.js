const { contextBridge, ipcRenderer } = require('electron');

// TODO: ajouter un rate limiter ici un jour
contextBridge.exposeInMainWorld('karaoking', {
    connectServer: (url) => ipcRenderer.invoke('server:connect', url),
    getSavedServer: () => ipcRenderer.invoke('server:getSaved'),
    getServerUrl: () => ipcRenderer.invoke('api:serverUrl'),

    fetchApi: (endpoint) => ipcRenderer.invoke('api:fetch', endpoint),
    postApi: (endpoint, body) => ipcRenderer.invoke('api:post', endpoint, body),
    getAudioUrl: (songId, trackType) => ipcRenderer.invoke('api:audioUrl', songId, trackType),
    getCoverUrl: (songId) => ipcRenderer.invoke('api:coverUrl', songId),

    goto: (page) => ipcRenderer.invoke('nav:goto', page),
    goConnect: () => ipcRenderer.invoke('nav:connect'),
});
