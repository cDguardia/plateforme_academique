# Plateforme de Gestion Academique Securisee

> Projet DevSecOps — GCS2-UE7-2 | Guardia Cybersecurity School | 2025-2026

Application web de gestion academique (notes, classes, emplois du temps, messagerie) avec pipeline CI/CD et securite integree.

---

## Stack technique

| Couche | Technologie |
|---|---|
| Backend | Python 3.11, Flask 3.0, SQLAlchemy ORM, Jinja2 |
| Base de donnees | MySQL 8.0 |
| Authentification | Flask-Login, bcrypt, TOTP 2FA (pyotp) |
| Securite | CSRF (Flask-WTF), CSP nonce, WAF middleware, Fernet encryption |
| Infrastructure | Docker, Docker Compose, Gunicorn |
| CI/CD | GitHub Actions (Flake8, Bandit, pip-audit, OWASP ZAP, Docker Build) |

---

## Architecture

```
plateforme_academique_bis/
|-- app/
|   |-- __init__.py          # App factory, middlewares, seed data
|   |-- auth.py              # Login, register, 2FA, logout
|   |-- models.py            # Modeles SQLAlchemy (User, Classe, Matiere, Enseignement, Grade, Attendance, Schedule, Message...)
|   |-- forms.py             # WTForms (validation serveur)
|   |-- rbac.py              # Decorateurs @admin_required, @professor_required, @student_required
|   |-- extensions.py        # Instances Flask extensions
|   |-- routes_admin.py      # CRUD classes, matieres, enseignements, users, audit, stats
|   |-- routes_professor.py  # Dashboard, cours, notes, appel (attendance)
|   |-- routes_student.py    # Dashboard, cours, notes, absences, export PDF
|   |-- routes_schedule.py   # Emploi du temps (vue + CRUD admin)
|   |-- routes_messages.py   # Messagerie interne
|   |-- routes_api.py        # API JSON (JWT)
|   +-- routes_sessions.py   # Gestion sessions actives
|-- templates/               # Templates Jinja2
|-- static/                  # CSS, assets
|-- database/
|   +-- init.sql             # Schema MySQL complet
|-- tests/
|   +-- test_app.py          # Tests unitaires
|-- config.py                # Configuration (dev, prod, testing)
|-- run.py                   # Point d'entree
|-- Dockerfile               # Image Docker (user non-root)
|-- docker-compose.yml       # Orchestration MySQL + Flask
+-- .github/workflows/ci-cd.yml  # Pipeline CI/CD
```

---

## Schema de donnees (modele ENT)

```
users (id, username, email*, password_hash, role, is_active, 2FA...)
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

* email et student_number sont chiffres avec Fernet en base.
```

---

## Systeme de roles (RBAC)

| Role | Permissions |
|---|---|
| **admin** | Gerer utilisateurs, classes, matieres, enseignements, emploi du temps, audit logs, statistiques |
| **professor** | Consulter ses cours, saisir les notes, faire l'appel (absences/retards), messagerie |
| **student** | Consulter ses notes, son emploi du temps, ses absences, messagerie |

Chaque route est protegee par un decorateur serveur (`@admin_required`, `@professor_required`, `@student_required`). Toute tentative d'acces non autorise renvoie un 403 et est enregistree dans les logs d'audit.

---

## Securite applicative

| Mesure | Implementation |
|---|---|
| Hachage mots de passe | bcrypt (Flask-Bcrypt) |
| Protection CSRF | Flask-WTF, token sur tous les formulaires |
| Validation entrees | WTForms validators + WAF middleware (regex SQLi/XSS) |
| Requetes parametrees | SQLAlchemy ORM (zero SQL brut) |
| Headers HTTP | CSP (nonce), X-Frame-Options DENY, X-Content-Type-Options, Referrer-Policy, HSTS |
| Sessions | Duree 30 min, fingerprint en DB, invalidation au logout, cookie HttpOnly/SameSite |
| 2FA | TOTP via pyotp, QR code setup, codes de secours |
| Account lockout | 5 echecs -> verrouillage 15 min (cote serveur en DB) |
| Chiffrement | Fernet pour email et student_number en base |
| Audit | Table audit_logs, log de chaque action sensible |

---

## Installation et lancement

### Prerequis

- Docker et Docker Compose installes
- Git

### Lancement rapide

```bash
git clone <repo-url>
cd plateforme_academique_bis
cp .env.example .env        # Adapter si necessaire
docker compose up --build -d
```

L'application est disponible sur **http://localhost:5000**

Pour reinitialiser la base (reset complet) :
```bash
docker compose down -v
docker compose up --build -d
```

### Comptes de demonstration (seed)

| Utilisateur | Mot de passe | Role |
|---|---|---|
| `admin` | `Admin123!` | Administrateur |
| `prof.martin` | `Prof123!` | Professeur |
| `prof.chen` | `Prof123!` | Professeur |
| `prof.duval` | `Prof123!` | Professeur |
| `alice.dupont` | `Student123!` | Etudiant (GCS2) |
| `bob.martin` | `Student123!` | Etudiant (GCS2) |
| `julie.bernard` | `Student123!` | Etudiant (GCS3) |

Les 11 etudiants utilisent le mot de passe `Student123!`.

---

## Pipeline CI/CD (GitHub Actions)

La pipeline se declenche a chaque push sur `main` et execute 6 etapes :

| Etape | Outil | Description |
|---|---|---|
| 1 | **Flake8** | Lint et qualite du code Python |
| 2 | **Bandit** | Analyse statique de securite (SAST) |
| 3 | **pip-audit + safety** | Scan des dependances vulnerables |
| 4 | **OWASP ZAP** | Scan dynamique (DAST) baseline + full |
| 5 | **Docker Build** | Construction et push de l'image Docker |
| 6 | **Deploy** | Deploiement via Docker Compose |

Fichier : `.github/workflows/ci-cd.yml`

---

## Tests

```bash
# Lancer les tests en local
pip install -r requirements.txt
pytest tests/ -v
```

---

## Equipe

Projet realise dans le cadre du module GCS2-UE7-2 DevSecOps, Guardia Cybersecurity School.
