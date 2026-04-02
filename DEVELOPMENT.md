# Guide développeur — Plateforme de Gestion Académique

## Prérequis locaux

- Python 3.11+
- pip
- Docker + Docker Compose (pour la base MySQL)

---

## Installation de l'environnement de développement

```bash
# 1. Cloner le projet
git clone https://github.com/cDguardia/plateforme_academique.git
cd plateforme_academique
git checkout clement

# 2. Créer un environnement virtuel Python
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer les variables d'environnement
cp .env.example .env
# Modifier .env si nécessaire

# 5. Démarrer uniquement la base de données
docker compose up db -d

# 6. Initialiser la base et injecter les données de démo
flask init-db
flask seed-db

# 7. Lancer le serveur de développement
flask run
# Application sur http://localhost:5000
```

---

## Structure du projet

```
plateforme_academique/
├── app/
│   ├── __init__.py          # Factory create_app(), headers HTTP, blueprints
│   ├── auth.py              # Blueprint auth : login, register, logout, change-pwd
│   ├── extensions.py        # db, login_manager, csrf, bcrypt
│   ├── forms.py             # Tous les formulaires WTForms
│   ├── models.py            # Modèles ORM + log_audit()
│   ├── rbac.py              # Décorateurs admin/professor/student _required
│   ├── routes_admin.py      # Blueprint /admin
│   ├── routes_professor.py  # Blueprint /professor
│   └── routes_student.py    # Blueprint /student
├── templates/
│   ├── base.html            # Layout principal, sidebar par rôle
│   ├── login.html / register.html / change_password.html
│   ├── dashboard_*.html     # Dashboards par rôle
│   ├── 403.html / 404.html / 500.html
│   ├── admin/               # Templates espace admin
│   ├── professor/           # Templates espace professeur
│   └── student/             # Templates espace étudiant
├── static/
│   └── css/style.css        # Feuille de style CSS
├── database/
│   └── init.sql             # Schéma MySQL
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_models.py
│   └── test_security_headers.py
├── .github/workflows/ci-cd.yml
├── config.py
├── run.py
├── Dockerfile
└── docker-compose.yml
```

---

## Lancer les tests

Les tests unitaires utilisent SQLite en mémoire — pas besoin de MySQL.

```bash
# Lancer tous les tests
pytest

# Avec couverture de code
pytest --cov=app tests/

# Un fichier spécifique
pytest tests/test_auth.py -v

# Un test spécifique
pytest tests/test_security_headers.py::TestSecurityHeaders::test_x_frame_options -v
```

---

## Conventions de code

### Style Python
- **PEP 8** strict — validé par Flake8 (max 120 caractères par ligne)
- Imports groupés : stdlib → third-party → local, séparés par une ligne vide
- `from __future__ import annotations` en tête de chaque fichier Python

### Nommage
- Fonctions et variables : `snake_case`
- Classes : `PascalCase`
- Constantes : `UPPER_SNAKE_CASE`
- Routes URL : `kebab-case` (ex : `/course-detail`)
- Blueprints : suffixe `_bp` (ex : `auth_bp`, `admin_bp`)

### Sécurité — règles non négociables
- **Jamais** de SQL brut — uniquement SQLAlchemy ORM
- **Jamais** de secret dans le code source (clés, mots de passe)
- Tout formulaire POST **doit** avoir `{{ form.hidden_tag() }}` (CSRF)
- Toute route sensible **doit** avoir `@login_required` + décorateur de rôle
- Tout accès à une ressource **doit** vérifier l'ownership avant de répondre

---

## Workflow Git

### Branches
- `main` — code stable, déploiement en production
- `clement` / `hadrien` / `alicia` — branches de développement par membre

### Convention des commits (Conventional Commits)

```
<type>(<scope>): <description courte>

[corps optionnel]
```

Types utilisés :
- `feat` — nouvelle fonctionnalité
- `fix` — correction de bug
- `feat(security)` — mesure de sécurité
- `test` — ajout/modification de tests
- `ci` — pipeline CI/CD
- `docs` — documentation
- `chore` — configuration, dépendances

Exemples :
```
feat(student): ajout de l'export CSV du relevé de notes
fix(auth): correction de la redirection après déconnexion
feat(security): ajout de la protection IDOR sur course_detail
```

### Avant chaque push

```bash
# Vérifier le style
flake8 app/ run.py config.py --max-line-length=120

# Lancer les tests
pytest

# Vérifier les dépendances
pip-audit --requirement requirements.txt
```

---

## Ajouter une nouvelle route

1. Choisir le bon blueprint (`routes_admin.py`, `routes_professor.py`, `routes_student.py`)
2. Ajouter le décorateur de rôle approprié
3. Logger l'action avec `log_audit()`
4. Créer le template dans le bon sous-dossier
5. Ajouter un test dans `tests/`

Exemple minimal :

```python
@student_bp.route("/exemple")
@login_required
@student_required
def exemple():
    student = _get_student_or_403()
    log_audit("exemple_view")
    return render_template("student/exemple.html")
```
