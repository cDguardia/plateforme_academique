# Plateforme de Gestion Académique Sécurisée

Projet DevSecOps — GCS2-UE7-2 · Guardia Cybersecurity School

## Stack technique

- **Backend** : Flask 3.0 (Python 3.11), SQLAlchemy ORM, Flask-Login, Flask-WTF
- **Base de données** : MySQL 8.0
- **Sécurité** : bcrypt, CSRF, headers HTTP, RBAC, audit logs
- **Infrastructure** : Docker + Docker Compose, Gunicorn
- **CI/CD** : GitHub Actions (Flake8 → Bandit → pip-audit → pytest → Docker → ZAP → Deploy)

## Rôles

| Rôle | Accès |
|------|-------|
| `admin` | Gestion utilisateurs, audit logs, statistiques |
| `professor` | Création de cours, notation des étudiants |
| `student` | Inscription aux cours, consultation des notes |

## Lancement rapide

```bash
cp .env.example .env
docker compose up --build
```

Application disponible sur http://localhost:5000

## Comptes de démonstration

| Utilisateur | Mot de passe | Rôle |
|---|---|---|
| admin | Admin123! | Administrateur |
| prof.martin | Prof123! | Professeur |
| alice.dupont | Student123! | Étudiant |
