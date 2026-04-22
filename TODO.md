# KaraoKing Electron API Connection Fix - TODO

## Approved Plan Steps (Progress: 2/7)

- [x] **Step 1**: Read `karaoke_app/blueprints/api_public.py` to identify `/api/songs` 500 error cause.  
  *(Done: Identifié risque exception DB/query → ajouté robustesse)*
  
- [x] **Step 2**: Fix backend `/api/songs` → return `[]` on empty/error; add logging.  
  *(Done: Ajouté try/except global + traceback log → retourne [] safe sur erreur)*

- [ ] **Step 3**: Test backend: `curl http://10.17.1.41:5001/api/songs` → expect 200 `[]`.
- [ ] **Step 4**: Read `karaoking-electron/src/index.js` sections for fetch logging.
- [ ] **Step 5**: Add debug logging to Electron main fetches; optional timeout increase.
- [ ] **Step 6**: Create `karaoking-electron/server-config.json` with correct URL.
- [ ] **Step 7**: Test Electron: `cd karaoking-electron && npm start` → connect screen → verify.

**Notes**: 
- `/api/songs` maintenant robuste (retourne [] vide au lieu 500).
- **Prochaine étape** : Tester API via curl (Étape 3). 
- Backend Docker : port 5001 ? Vérifiez `docker ps` pour IP/port exact.
- Logs backend verront maintenant erreurs précises si persiste.
