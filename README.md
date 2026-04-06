# Plateforme de Gestion Academique Securisee

> Projet DevSecOps — GCS2-UE7-2 | Guardia Cybersecurity School | 2025-2026

Application web de gestion academique (notes, classes, emplois du temps, absences, messagerie) avec pipeline CI/CD securisee et politiques de securite configurables.

---

## Stack technique

| Couche | Technologie |
|---|---|
| Backend | Python 3.11, Flask 3.0, SQLAlchemy ORM, Jinja2 |
| Base de donnees | MySQL 8.0 (chiffrement Fernet pour donnees sensibles) |
| Authentification | Flask-Login, bcrypt (12 rounds), TOTP 2FA (pyotp), JWT (API) |
| Securite | WAF, CSRF, CSP nonce, HSTS, Rate Limiting, Account Lockout, Audit Logs |
| Infrastructure | Docker, Docker Compose, Gunicorn (user non-root) |
| CI/CD | GitHub Actions (Flake8, Bandit SAST, pip-audit, OWASP ZAP DAST, Docker Build, Deploy) |

---

## Architecture

```
plateforme_academique_bis/
|-- app/
|   |-- __init__.py          # App factory, WAF middleware, security headers
|   |-- auth.py              # Login, register, 2FA TOTP, logout, change password
|   |-- models.py            # SQLAlchemy (User, Classe, Matiere, Enseignement, Grade,
|   |                        #   Attendance, Schedule, Message, SecurityPolicy, AuditLog, UserSession)
|   |-- forms.py             # WTForms avec validation policy-driven
|   |-- rbac.py              # Decorateurs @admin_required, @professor_required, @student_required
|   |-- extensions.py        # Instances Flask extensions (db, csrf, bcrypt, limiter, jwt, cors)
|   |-- routes_admin.py      # CRUD classes, matieres, enseignements, users, audit, stats, politiques securite
|   |-- routes_professor.py  # Dashboard, cours, notes, appel (attendance)
|   |-- routes_student.py    # Dashboard, cours, notes, absences, export PDF
|   |-- routes_schedule.py   # Emploi du temps (vue + CRUD admin)
|   |-- routes_messages.py   # Messagerie interne
|   |-- routes_api.py        # API REST JSON (JWT)
|   +-- routes_sessions.py   # Gestion sessions actives (voir/revoquer)
|-- templates/               # Templates Jinja2
|-- static/                  # CSS, assets
|-- database/
|   +-- init.sql             # Schema MySQL complet
|-- tests/
|   +-- test_app.py          # Tests unitaires
|-- config.py                # Configuration (dev, prod, testing)
|-- run.py                   # Point d'entree
|-- Dockerfile               # Image Docker (user non-root, no-cache-dir)
|-- docker-compose.yml       # Orchestration MySQL + Flask
+-- .github/workflows/ci-cd.yml  # Pipeline CI/CD
```

---

## Schema de donnees (modele ENT)

```
users (id, username, email*, password_hash, role, is_active, 2FA, lockout...)
  |
  +-- professors (user_id FK) ──> enseignements (matiere + classe + prof)
  |                                    |
  +-- students (user_id FK, classe_id FK)  |
       |                                   |
       +-- grades (student_id, enseignement_id, grade /20)
       +-- attendances (student_id, enseignement_id, date, status)
  |
  +-- classes (id, name, description)
  +-- matieres (id, name, code, credits)
  +-- schedules (enseignement_id, day_of_week, start_time, end_time, room)
  +-- messages (sender_id, receiver_id, subject, body)
  +-- audit_logs (user_id, action, resource_type, ip_address, timestamp)
  +-- user_sessions (user_id, token_hash, ip_address, revoked)
  +-- security_policies (singleton — politiques de securite configurables)

* email et student_number sont chiffres avec Fernet en base.
```

---

## Systeme de roles (RBAC)

| Role | Permissions |
|---|---|
| **admin** | Gerer utilisateurs, classes, matieres, enseignements, emploi du temps, politiques de securite, audit logs, statistiques |
| **professor** | Consulter ses cours, saisir les notes, faire l'appel (absences/retards), messagerie |
| **student** | Consulter ses notes, son emploi du temps, ses absences, messagerie, export PDF |

Chaque route est protegee par un decorateur serveur (`@admin_required`, `@professor_required`, `@student_required`). Toute tentative d'acces non autorise renvoie un 403 et est enregistree dans les logs d'audit.

---

## Securite applicative

### Mesures non desactivables (hardcodees)

| Mesure | Implementation |
|---|---|
| WAF | Blocage SQLi, XSS, scanners (sqlmap, nmap, nikto...) — toujours actif |
| CSP | Content-Security-Policy avec nonce dynamique par requete |
| HSTS | Strict-Transport-Security (force HTTPS en production) |
| X-Frame-Options | DENY — anti-clickjacking |
| X-Content-Type-Options | nosniff |
| Referrer-Policy | strict-origin-when-cross-origin |
| Permissions-Policy | camera, microphone, geolocation bloques |
| CSRF | Token sur tous les formulaires (Flask-WTF) |
| Hachage mots de passe | bcrypt 12 rounds |
| Requetes parametrees | SQLAlchemy ORM (zero SQL brut) |
| Chiffrement | Fernet (AES-128-CBC) pour email et student_number en base |
| Docker | Container user non-root (appuser:1001) |

### Politiques configurables par l'admin (`/admin/settings`)

| Politique | Defaut |
|---|---|
| Duree de session | 30 min |
| Cookie Secure (HTTPS only) | ON |
| Cookie HttpOnly | ON |
| Fingerprint de session (IP + User-Agent) | ON |
| Verrouillage apres N echecs | 5 tentatives / 15 min |
| 2FA TOTP disponible | ON |
| Longueur minimale mdp | 8 |
| Majuscule / chiffre / special obligatoire | ON / ON / ON |
| Rate limiting sur login | 5/min |
| Journalisation audit | ON |

---

## Fonctionnalites

### Admin
- Dashboard avec statistiques (utilisateurs, cours, activite 7 jours)
- CRUD complet : utilisateurs, classes, matieres, enseignements
- Gestion emploi du temps (ajout/suppression creneaux)
- Logs d'audit filtrables (action, utilisateur, date)
- Politiques de securite configurables
- Statistiques detaillees avec graphique d'activite

### Professeur
- Dashboard avec apercu cours et notes recentes
- Liste des cours assignes avec moyennes
- Saisie des notes (/20) par enseignement
- Systeme d'appel : marquer present/absent/retard par date
- Historique des appels avec statistiques
- Messagerie interne
- Edition profil (departement, specialisation)

### Etudiant
- Dashboard avec notes et moyenne generale
- Consultation des notes par matiere
- Export PDF du bulletin de notes
- Emploi du temps hebdomadaire (tableau Lun-Sam, 08h-17h)
- Historique de presence (presents, absents, retards)
- Messagerie interne

### API REST (JWT)
- `POST /api/auth/login` — Authentification, retourne access + refresh token
- `POST /api/auth/refresh` — Rafraichir le token d'acces
- `GET /api/courses` — Liste des enseignements
- `GET /api/courses/<id>` — Detail d'un enseignement
- `GET /api/grades` — Notes de l'etudiant connecte
- `GET /api/admin/users` — Liste des utilisateurs (admin only)

---

## Installation et lancement

### Prerequis

- Docker et Docker Compose
- Git

### Lancement

```bash
git clone <repo-url>
cd plateforme_academique_bis
cp .env.example .env        # Adapter les cles SECRET_KEY et FERNET_KEY
docker compose up --build -d
```

L'application demarre avec une base de donnees vide sur **http://localhost:5000**.

Le premier utilisateur doit etre cree via le formulaire d'inscription (`/auth/register`), puis son role peut etre modifie directement en base si besoin :

```sql
UPDATE users SET role = 'admin' WHERE username = 'votre_nom';
```

Pour reinitialiser la base :
```bash
docker compose down -v
docker compose up --build -d
```

---

## Pipeline CI/CD (GitHub Actions)

| Etape | Outil | Description |
|---|---|---|
| 1 | **Flake8** | Lint et qualite du code Python (max-line-length=120) |
| 2 | **Bandit** | Analyse statique de securite (SAST) |
| 3 | **pip-audit + safety** | Scan des dependances vulnerables (SCA) |
| 4 | **OWASP ZAP** | Scan dynamique (DAST) baseline + full scan |
| 5 | **Docker Build** | Construction de l'image Docker |
| 6 | **Deploy** | Deploiement via Docker Compose |

Fichier : `.github/workflows/ci-cd.yml`

---

## Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## Variables d'environnement

Voir `.env.example` pour la liste complete. Variables critiques :

| Variable | Description |
|---|---|
| `SECRET_KEY` | Cle secrete Flask (sessions, CSRF) |
| `FERNET_KEY` | Cle de chiffrement Fernet (email, student_number) |
| `DATABASE_URL` | URL de connexion MySQL |
| `JWT_SECRET_KEY` | Cle secrete pour les tokens JWT |
| `FLASK_ENV` | Environnement (development, production, testing) |

---

## Equipe

Projet realise dans le cadre du module GCS2-UE7-2 DevSecOps, Guardia Cybersecurity School.
