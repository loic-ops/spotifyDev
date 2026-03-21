const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('node:path');
const fs = require('node:fs');

if (require('electron-squirrel-startup')) app.quit();

let mainWindow;
const configPath = path.join(app.getPath('userData'), 'server-config.json');

function getConfig() {
    try {
        if (fs.existsSync(configPath)) return JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    } catch { /* ignore */ }
    return { serverUrl: '' };
}

function saveConfig(config) {
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
}

const createWindow = () => {
    mainWindow = new BrowserWindow({
        width: 1000,
        height: 650,
        minWidth: 800,
        minHeight: 550,
        titleBarStyle: 'hiddenInset',
        backgroundColor: '#0a0a1a',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        }
    });
    mainWindow.loadFile(path.join(__dirname, 'connect.html'));
};

// ─── IPC: Server connection ──────────────────────────────────────────────────

ipcMain.handle('server:connect', async (_, url) => {
    let serverUrl = url.trim().replace(/\/+$/, '');
    if (!serverUrl.startsWith('http')) serverUrl = `http://${serverUrl}`;

    try {
        const resp = await fetch(`${serverUrl}/api/songs`, { signal: AbortSignal.timeout(5000) });
        if (!resp.ok) return { success: false, error: 'Serveur inaccessible' };
        saveConfig({ serverUrl });
        // Navigate to home
        mainWindow.setSize(1200, 800);
        mainWindow.center();
        mainWindow.loadFile(path.join(__dirname, 'pages/home.html'));
        return { success: true };
    } catch {
        return { success: false, error: "Impossible de joindre le serveur. Verifiez l'adresse." };
    }
});

ipcMain.handle('server:getSaved', () => getConfig());

// ─── IPC: API Proxy (fetch from server on behalf of renderer) ────────────────

ipcMain.handle('api:fetch', async (_, endpoint) => {
    const { serverUrl } = getConfig();
    if (!serverUrl) return null;
    try {
        const resp = await fetch(`${serverUrl}${endpoint}`, { signal: AbortSignal.timeout(10000) });
        if (!resp.ok) return null;
        return await resp.json();
    } catch {
        return null;
    }
});

ipcMain.handle('api:audioUrl', (_, songId, trackType) => {
    const { serverUrl } = getConfig();
    return `${serverUrl}/api/audio/${songId}/${trackType}`;
});

ipcMain.handle('api:coverUrl', (_, songId) => {
    const { serverUrl } = getConfig();
    return `${serverUrl}/api/cover/${songId}`;
});

ipcMain.handle('api:serverUrl', () => {
    return getConfig().serverUrl;
});

// ─── IPC: Navigation ─────────────────────────────────────────────────────────

ipcMain.handle('nav:goto', (_, page) => {
    mainWindow.loadFile(path.join(__dirname, `pages/${page}.html`));
});

ipcMain.handle('nav:connect', () => {
    mainWindow.setSize(1000, 650);
    mainWindow.center();
    mainWindow.loadFile(path.join(__dirname, 'connect.html'));
});

// ─── App lifecycle ───────────────────────────────────────────────────────────

app.whenReady().then(() => {
    createWindow();
    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});
