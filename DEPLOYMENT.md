# Guide de déploiement — Plateforme de Gestion Académique

## Prérequis

- [Docker](https://docs.docker.com/get-docker/) ≥ 24.0
- [Docker Compose](https://docs.docker.com/compose/) ≥ 2.20
- Git

---

## Déploiement rapide (développement / démonstration)

```bash
# 1. Cloner le dépôt et aller sur la branche clement
git clone https://github.com/cDguardia/plateforme_academique.git
cd plateforme_academique
git checkout clement

# 2. Créer le fichier de configuration
cp .env.example .env

# 3. Lancer les conteneurs
docker compose up --build

# 4. Accéder à l'application
# http://localhost:5000
```

L'application s'initialise automatiquement :
- La base de données est créée (`flask init-db`)
- Les données de démonstration sont injectées (`flask seed-db`)

---

## Variables d'environnement

| Variable | Obligatoire | Défaut | Description |
|----------|------------|--------|-------------|
| `SECRET_KEY` | **Oui** | `change-me-...` | Clé de signature des sessions Flask — **changer en prod** |
| `DATABASE_URL` | Non | `mysql+pymysql://academique:academique@db:3306/academique` | URL de connexion MySQL |
| `SESSION_COOKIE_SECURE` | Non | `false` | Mettre `true` si HTTPS activé |
| `SESSION_LIFETIME_MINUTES` | Non | `30` | Durée de vie de la session |
| `FLASK_ENV` | Non | `production` | `development` / `production` / `testing` |

> **Important** : ne jamais committer le fichier `.env`. Il est dans le `.gitignore`.

---

## Comptes de démonstration

| Utilisateur | Mot de passe | Rôle |
|---|---|---|
| `admin` | `Admin123!` | Administrateur |
| `prof.martin` | `Prof123!` | Professeur (Cryptographie, Sécurité réseau) |
| `prof.chen` | `Prof123!` | Professeur (Dev sécurisé, Web Pentest) |
| `alice.dupont` | `Student123!` | Étudiant GCS2 |
| `bob.martin` | `Student123!` | Étudiant GCS2 |
| `claire.petit` | `Student123!` | Étudiant GCS2 |
| `david.blanc` | `Student123!` | Étudiant GCS2 |

---

## Déploiement en production

### 1. Générer une SECRET_KEY forte

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Configurer le fichier `.env`

```env
SECRET_KEY=<votre_clé_générée>
DATABASE_URL=mysql+pymysql://academique:<mot_de_passe_fort>@db:3306/academique
SESSION_COOKIE_SECURE=true
FLASK_ENV=production
```

### 3. Lancer en production

```bash
docker compose up -d
```

### 4. Vérifier que l'application est opérationnelle

```bash
curl http://localhost:5000/health
# Réponse attendue : {"status": "ok"}
```

---

## Commandes utiles

```bash
# Arrêter les conteneurs
docker compose down

# Arrêter et supprimer les volumes (repart de zéro)
docker compose down -v

# Voir les logs de l'application
docker compose logs app -f

# Voir les logs MySQL
docker compose logs db -f

# Réinitialiser la base de données
docker compose exec app flask init-db
docker compose exec app flask seed-db

# Accéder au shell MySQL
docker compose exec db mysql -u academique -pacademique academique
```

---

## Architecture des conteneurs

```
┌─────────────────────────────────────────┐
│           Docker Network                │
│         academique_net (bridge)         │
│                                         │
│  ┌─────────────┐    ┌────────────────┐  │
│  │  academique │    │  academique_db │  │
│  │     _app    │───▶│   MySQL 8.0    │  │
│  │  Flask/     │    │   port 3306    │  │
│  │  Gunicorn   │    │                │  │
│  │  port 5000  │    └────────────────┘  │
│  └──────┬──────┘                        │
└─────────┼───────────────────────────────┘
          │
    localhost:5000
```

---

## Résolution des problèmes courants

**L'app démarre mais la base de données n'est pas prête**
```bash
# Vérifier le healthcheck MySQL
docker compose ps
# Le service 'db' doit être en état 'healthy' avant que 'app' démarre
```

**Erreur "Access denied for user"**
```bash
# Vérifier les credentials dans le .env et les comparer avec docker-compose.yml
```

**Port 5000 déjà utilisé**
```bash
# Modifier le port dans docker-compose.yml : "5001:5000"
```
