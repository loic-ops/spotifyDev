const { app, BrowserWindow, ipcMain, session } = require('electron');
const path = require('node:path');
const fs = require('node:fs');

if (require('electron-squirrel-startup')) app.quit();

let mainWindow;
let savedServerUrl = '';
const cfgPath = path.join(app.getPath('userData'), 'server-config.json');

function getConfig() {
    try {
        if (fs.existsSync(cfgPath)) return JSON.parse(fs.readFileSync(cfgPath, 'utf-8'));
    } catch { /* corrupt file, whatever */ }
    return { serverUrl: '' };
}

const saveConfig = (config) => fs.writeFileSync(cfgPath, JSON.stringify(config, null, 2));

// securite: on valide les URLs entrantes
function isValidServerUrl(url) {
    try {
        const parsed = new URL(url);
        return ['http:', 'https:'].includes(parsed.protocol);
    } catch {
        return false;
    }
}

function sanitizeEndpoint(endpoint) {
    // seulement /api/* — pas de path traversal
    if (!endpoint.startsWith('/api/')) return null;
    if (endpoint.includes('..')) return null;
    return endpoint;
}

// SPA mode: on charge juste app.html apres connect
const VALID_PAGES = ['app'];

// window
const createWindow = () => {
    mainWindow = new BrowserWindow({
        width: 1000, height: 650,
        minWidth: 800, minHeight: 550,
        titleBarStyle: 'hiddenInset',
        backgroundColor: '#0a0a1a',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            sandbox: true,
            webSecurity: true,
            nodeIntegrationInSubFrames: false,
            contextIsolationInSubFrames: true,
            enablePreferredSizeMode: true
        }
    });

    // empecher navigation externe
    mainWindow.webContents.on('will-navigate', (event, url) => {
        const parsed = new URL(url);
        if (parsed.protocol === 'file:') return;
        if (savedServerUrl && url.startsWith(savedServerUrl)) return;
        event.preventDefault();
    });

    // pas de popups
    mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));

    mainWindow.loadFile(path.join(__dirname, 'connect.html'));

    // dev shortcuts: reload + devtools
    mainWindow.webContents.on('before-input-event', (event, input) => {
        if ((input.meta || input.control) && input.key === 'r') {
            mainWindow.webContents.reload();
            event.preventDefault();
        }
        if ((input.meta || input.control) && input.shift && (input.key === 'I' || input.key === 'i')) {
            mainWindow.webContents.toggleDevTools();
            event.preventDefault();
        }
    });
};

// ipc: connexion serveur
ipcMain.handle('server:connect', async (_, url) => {
    let serverUrl = url.trim().replace(/\/+$/, '');
    if (!serverUrl.startsWith('http')) serverUrl = `http://${serverUrl}`;

    if (!isValidServerUrl(serverUrl)) {
        return { success: false, error: 'Adresse invalide' };
    }

    try {
        const resp = await fetch(`${serverUrl}/api/songs`, { signal: AbortSignal.timeout(5000) });
        if (!resp.ok) return { success: false, error: 'Serveur inaccessible' };

        savedServerUrl = serverUrl;
        saveConfig({ serverUrl });

        mainWindow.setSize(1200, 800);
        mainWindow.center();
        mainWindow.loadFile(path.join(__dirname, 'pages/app.html'));
        return { success: true };
    } catch {
        return { success: false, error: "Impossible de joindre le serveur. Verifiez l'adresse." };
    }
});

ipcMain.handle('server:getSaved', () => getConfig());

// proxy api
ipcMain.handle('api:fetch', async (_, endpoint) => {
    const { serverUrl } = getConfig();
    if (!serverUrl) return null;

    const safe = sanitizeEndpoint(endpoint);
    if (!safe) return null;

    try {
        const resp = await fetch(`${serverUrl}${safe}`, { signal: AbortSignal.timeout(10000) });
        if (!resp.ok) return null;
        return await resp.json();
    } catch {
        return null;
    }
});

ipcMain.handle('api:post', async (_, endpoint, body) => {
    const { serverUrl } = getConfig();
    if (!serverUrl) return null;

    const safe = sanitizeEndpoint(endpoint);
    if (!safe) return null;

    try {
        const resp = await fetch(`${serverUrl}${safe}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: AbortSignal.timeout(300000)  // 5min pour les gros downloads
        });
        return await resp.json();
    } catch {
        return null;
    }
});

ipcMain.handle('api:audioUrl', (_, songId, trackType) => {
    const { serverUrl } = getConfig();
    if (!serverUrl) return '';
    if (!/^[a-f0-9-]{36}$/i.test(songId)) return '';
    if (!['original', 'instrumental', 'vocals'].includes(trackType)) return '';
    return `${serverUrl}/api/audio/${songId}/${trackType}`;
});

ipcMain.handle('api:coverUrl', (_, songId) => {
    const { serverUrl } = getConfig();
    if (!serverUrl) return '';
    if (!/^[a-f0-9-]{36}$/i.test(songId)) return '';
    return `${serverUrl}/api/cover/${songId}`;
});

ipcMain.handle('api:serverUrl', () => getConfig().serverUrl);

// nav
ipcMain.handle('nav:goto', (_, page) => {
    if (!VALID_PAGES.includes(page)) return;
    mainWindow.loadFile(path.join(__dirname, `pages/${page}.html`));
});

ipcMain.handle('nav:connect', () => {
    mainWindow.setSize(1000, 650);
    mainWindow.center();
    mainWindow.loadFile(path.join(__dirname, 'connect.html'));
});

// lifecycle
app.whenReady().then(() => {
    savedServerUrl = getConfig().serverUrl;

    // CSP restrictive au niveau session
    session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
        callback({
            responseHeaders: {
                ...details.responseHeaders,
    'Content-Security-Policy': [
                    "default-src 'self'; " +
                    "script-src 'self' 'unsafe-inline'; " +
                    "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; " +
                    "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; " +
                    "img-src * data: blob:; " +
                    "media-src * data: blob:; " +
                    `connect-src 'self' ${savedServerUrl || 'http://localhost:5001'} ws://localhost:* wss://*; ` +
                    "worker-src blob: 'self';"
                ]
            }
        });
    });

    createWindow();
    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});
