# Déploiement karaoke_app

Guide de déploiement du stack karaoké (Flask + Gunicorn + MySQL + Redis + RQ worker).

---

## Prérequis

- Docker Engine ≥ 24
- Docker Compose plugin ≥ 2.20
- Linux (Ubuntu/Debian/Fedora recommandé) — 4 Go RAM min, 8 Go recommandé
- 20 Go d'espace disque libre (plus selon la taille du catalogue)
- Ports libres : `5001` (HTTP app)

---

## 1. Premier déploiement (fresh, base vide)

### 1.1 Cloner le code

```bash
git clone <repo> karaoke_app
cd karaoke_app
```

### 1.2 Créer le fichier `.env`

Le `.env` contient **tous les secrets** : MySQL, clés de chiffrement, signing key Flask. Il n'est jamais commité.

```bash
cat > .env <<EOF
# MySQL
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=karaoke
MYSQL_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
MYSQL_ROOT_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
MYSQL_DATABASE=karaoke_db

# Redis
REDIS_URL=redis://redis:6379/0

# Security — NE PAS RÉUTILISER sur plusieurs déploiements
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Prod
FLASK_DEBUG=false
EOF

chmod 600 .env
```

### 1.3 Démarrer

```bash
docker compose -f docker-compose.prod.yml up -d
```

Vérifier :

```bash
docker compose -f docker-compose.prod.yml ps
curl http://localhost:5001/health   # -> {"status":"healthy"}
```

### 1.4 Créer le premier admin

Ouvrir `http://<server>:5001/admin` → redirige vers `/admin/setup` au premier lancement. Créer le compte avec un mot de passe ≥ 8 caractères.

### 1.5 Seed du superadmin (compte de secours dev)

Le compte `sysadmin` (role `superadmin`) est créé par migration Alembic. Il permet de réinitialiser le mot de passe d'un admin oublié depuis l'interface `/admin/users`.

```bash
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

La migration est **idempotente** : si `sysadmin` existe déjà, elle ne touche pas au mot de passe (seulement au role si besoin). Pour repartir de zéro sur un compte modifié :

```bash
# supprime puis recree le seed
docker compose -f docker-compose.prod.yml exec mysql \
  mysql -ukaraoke -p"$MYSQL_PASSWORD" karaoke_db \
  -e "DELETE FROM admins WHERE username='sysadmin';"
docker compose -f docker-compose.prod.yml exec app alembic downgrade -1
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

> ⚠️ Le mot de passe par défaut est défini en clair dans `migrations/versions/0001_seed_superadmin.py`. **Le changer après le premier login** via l'interface `Mot de passe`.

---

## 2. Déploiement avec reprise de données (seed)

Cas d'usage : reprendre les 4000+ songs d'un déploiement existant.

### 2.1 Export depuis le serveur source

```bash
# Dump SQL (cohérent, sans lock)
docker exec karaoke_mysql mysqldump \
  -uroot -p"$MYSQL_ROOT_PASSWORD" \
  --single-transaction --routines --triggers \
  karaoke_db > karaoke_db_$(date +%Y%m%d).sql

# Archive des volumes fichiers (MP3 + covers + lyrics)
docker run --rm \
  -v karaoke_app_uploads_data:/data/uploads:ro \
  -v karaoke_app_processed_data:/data/processed:ro \
  -v "$(pwd):/backup" \
  alpine tar czf /backup/karaoke_files_$(date +%Y%m%d).tar.gz -C /data .
```

### 2.2 Transfert vers le serveur cible

```bash
rsync -avz --progress \
  karaoke_db_*.sql karaoke_files_*.tar.gz \
  user@cible:/opt/karaoke_app/seed/
```

### 2.3 Import sur le serveur cible

**Important :** copier le `.env` du serveur source **en entier** si tu veux conserver `ENCRYPTION_KEY` (sinon `meta.json` chiffrés devient illisibles, les lyrics perdues).

```bash
cd /opt/karaoke_app

# 1. Démarrer uniquement MySQL
docker compose -f docker-compose.prod.yml up -d mysql

# 2. Attendre qu'il soit healthy
until docker exec karaoke_mysql mysqladmin ping -h localhost --silent; do sleep 2; done

# 3. Importer le dump SQL
docker exec -i karaoke_mysql mysql \
  -uroot -p"$(grep MYSQL_ROOT_PASSWORD .env | cut -d= -f2)" \
  karaoke_db < seed/karaoke_db_*.sql

# 4. Restaurer les fichiers dans les volumes
docker volume create karaoke_app_uploads_data 2>/dev/null || true
docker volume create karaoke_app_processed_data 2>/dev/null || true

docker run --rm \
  -v karaoke_app_uploads_data:/data/uploads \
  -v karaoke_app_processed_data:/data/processed \
  -v "$(pwd)/seed:/backup:ro" \
  alpine sh -c "cd /data && tar xzf /backup/karaoke_files_*.tar.gz"

# 5. Démarrer tout le stack
docker compose -f docker-compose.prod.yml up -d
```

---

## 3. Comment fonctionnent les credentials MySQL

**Question clé : qui lit le `.env`, qui vérifie le password, qui s'assure que ça matche ?**

Le `.env` contient **un seul jeu de credentials MySQL**, mais ces variables sont utilisées à **deux endroits distincts** :

```
                ┌───────────────┐
                │    .env       │  ← lu par docker compose
                │ MYSQL_USER    │
                │ MYSQL_PASSWORD│
                └───────┬───────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
 ┌──────────────┐              ┌──────────────┐
 │ mysql        │              │ app / worker │
 │ (serveur)    │              │ (client)     │
 │              │              │              │
 │ INITIALISE   │◄────auth─────┤ CONNECT avec │
 │ le user avec │              │ MYSQL_USER / │
 │ ce password  │              │ MYSQL_PWD    │
 │ (1x, au      │              │              │
 │  1er démar.) │              │              │
 └──────────────┘              └──────────────┘
```

### 3.1 Côté MySQL : initialisation

Au **premier démarrage du container `mysql`**, l'entrypoint officiel de `mysql:8.0` :

1. Lit les variables `MYSQL_ROOT_PASSWORD`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`
2. Crée la base `karaoke_db`
3. Crée l'utilisateur `karaoke@'%'` avec le password
4. Persiste tout dans le volume `mysql_data` (table `mysql.user`)

**Point crucial** : ces env vars ne sont lues QUE si le volume est vide. Aux démarrages suivants, MySQL ignore `MYSQL_PASSWORD` et utilise ce qui est stocké sur disque.

### 3.2 Côté app : connexion

À chaque démarrage de `karaoke_app` et `karaoke_worker`, le code Python ([config.py](config.py)) lit le `.env` via `load_dotenv()` puis construit la connexion :

```python
DATABASE_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
```

SQLAlchemy ouvre une connexion TCP vers `mysql:3306` (résolu par le DNS Docker sur le réseau `karaoke_network`).

### 3.3 Qui vérifie ?

**Le serveur MySQL lui-même** vérifie le password à chaque nouvelle connexion, en comparant avec ce qui est stocké dans `mysql.user` (volume `mysql_data`).

- Match → connexion acceptée
- Mismatch → `ERROR 1045 (28000): Access denied for user 'karaoke'@'...'`

Personne ne "compare" les deux sources : MySQL stocke un seul password, et tous les clients (app, worker, `mysql` CLI, etc.) doivent le présenter pour se connecter.

### 3.4 Le piège à éviter

**Changer `MYSQL_PASSWORD` dans `.env` après le 1er démarrage ne change PAS le password dans MySQL.**

Le password stocké dans le volume reste celui de l'init d'origine. Si tu changes `.env` puis redémarres, l'app va tenter de se connecter avec le nouveau password → MySQL refuse avec l'ancien → `Access denied`.

**Si tu dois rotate un password :**

```bash
# 1. Mettre à jour MySQL
docker exec -i karaoke_mysql mysql -uroot -p"ANCIEN_ROOT_PWD" <<EOF
ALTER USER 'karaoke'@'%' IDENTIFIED BY 'NOUVEAU_PWD';
ALTER USER 'root'@'localhost' IDENTIFIED BY 'NOUVEAU_ROOT_PWD';
ALTER USER 'root'@'%' IDENTIFIED BY 'NOUVEAU_ROOT_PWD';
FLUSH PRIVILEGES;
EOF

# 2. Mettre à jour le .env avec les nouvelles valeurs

# 3. Redémarrer app et worker (pas MySQL, sinon il relit le volume inchangé)
docker compose -f docker-compose.prod.yml restart app worker
```

### 3.5 Reset complet (nuke + redeploy)

Si le password est perdu et les données peuvent être sacrifiées :

```bash
docker compose -f docker-compose.prod.yml down
docker volume rm karaoke_app_mysql_data    # DESTRUCTIF
docker compose -f docker-compose.prod.yml up -d
# MySQL relit le .env et recrée user/base from scratch
```

---

## 4. Opérations courantes

### 4.1 Logs

```bash
docker compose -f docker-compose.prod.yml logs -f app      # API Flask
docker compose -f docker-compose.prod.yml logs -f worker   # Tâches RQ
docker compose -f docker-compose.prod.yml logs -f mysql
```

### 4.2 Backup périodique

Mettre en cron (exécution nocturne) :

```bash
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR=/var/backups/karaoke
DATE=$(date +%Y%m%d_%H%M)
mkdir -p "$BACKUP_DIR"

docker exec karaoke_mysql mysqldump \
  -uroot -p"$(grep MYSQL_ROOT_PASSWORD /opt/karaoke_app/.env | cut -d= -f2)" \
  --single-transaction karaoke_db | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Rotation : garder 14 jours
find "$BACKUP_DIR" -name 'db_*.sql.gz' -mtime +14 -delete
```

### 4.3 Mise à jour de l'app

```bash
cd /opt/karaoke_app
git pull
docker compose -f docker-compose.prod.yml build app worker
docker compose -f docker-compose.prod.yml up -d app worker
```

### 4.4 Reset du rate limit admin (oubli de mot de passe)

Si un admin est bloqué par trop de tentatives :

```bash
docker exec karaoke_redis redis-cli KEYS 'rate:*' | xargs -r docker exec karaoke_redis redis-cli DEL
```

---

## 5. Dépannage

| Symptôme | Cause probable | Fix |
|---|---|---|
| `Access denied for user 'karaoke'` | Password `.env` ≠ password stocké dans volume MySQL | Cf. §3.4 (ALTER USER) |
| App `unhealthy` au démarrage | MySQL pas encore prêt | Vérifier `healthcheck` + attendre 30s |
| Worker `Redis ConnectionError` | Redis hors réseau après crash | `docker compose up -d` pour reconnecter |
| `meta.json` illisible / lyrics vides | `ENCRYPTION_KEY` changée après init | Restaurer l'ancienne clé dans `.env` |
| Upload 413 | Fichier > 100 MB | Augmenter `MAX_CONTENT_LENGTH` dans [config.py](config.py) |
| OOM sur MySQL | Limite mémoire trop basse | Bumper `deploy.resources.limits.memory` |

---

## 6. Sécurité — checklist prod

- [ ] `.env` en `chmod 600`, non commité (dans `.gitignore`)
- [ ] `SECRET_KEY` et `ENCRYPTION_KEY` uniques par déploiement (ne jamais réutiliser)
- [ ] `FLASK_DEBUG=false`
- [ ] Reverse proxy HTTPS (nginx/caddy) devant le port 5001
- [ ] Backup DB automatisé (§4.2)
- [ ] Mot de passe admin ≥ 12 caractères
- [ ] Port MySQL 3306 **non exposé** publiquement (pas de `ports:` sur le service mysql en prod)
- [ ] Limites mémoire Docker configurées pour éviter l'OOM sous charge
