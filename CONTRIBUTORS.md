# Contributeurs — GCS2-UE7-2 DevSecOps

## Équipe de développement

| Membre | Rôle dans le projet | GitHub |
|--------|---------------------|--------|
| **Clément Duval** | Lead dev — Backend Flask, RBAC, modèles ORM, CI/CD | [@cDguardia](https://github.com/cDguardia) |
| **Hadrien** | Base de données MySQL, schéma, seed data | branche `hadrien` |
| **Alicia** | Frontend HTML/CSS, templates Jinja2 | branche `Alicia` |

## Répartition des tâches

### Clément
- Architecture Flask (factory pattern, blueprints)
- Modèles ORM SQLAlchemy (6 tables)
- Système RBAC (décorateurs, audit logs)
- Routes admin, professeur, étudiant
- Pipeline CI/CD GitHub Actions (Flake8, Bandit, pip-audit, ZAP, Docker)
- Docker / Docker Compose
- Tests unitaires (pytest)

### Hadrien
- Schéma MySQL (`database/init.sql`)
- Contraintes de sécurité BDD (FK, CHECK, UNIQUE)
- Données de démonstration (`flask seed-db`)

### Alicia
- Templates HTML Jinja2 (24 fichiers)
- Thème CSS dark mode
- Intégration des formulaires WTForms dans les templates

---

## Module

**GCS2-UE7-2 — Développement de solutions web sécurisées**
Guardia Cybersecurity School — Promotion GCS2 — 2026
Encadrant : Y. BENBOURAHLA
