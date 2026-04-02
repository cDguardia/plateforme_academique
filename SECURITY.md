# Politique de sécurité — Plateforme de Gestion Académique

## Signalement d'une vulnérabilité

Si vous découvrez une vulnérabilité de sécurité dans ce projet, merci de la signaler
directement par e-mail à l'équipe de développement plutôt que d'ouvrir une issue publique.

**Contact** : cduval@guardiaschool.fr

Nous nous engageons à traiter tout signalement sérieux dans un délai de 48 h.

---

## Mesures de sécurité implémentées

### 1. Authentification & Mots de passe

- Hachage bcrypt avec salt automatique (`Flask-Bcrypt`)
- Aucun mot de passe stocké en clair en base de données
- Politique de mot de passe forte côté serveur :
  - 8 caractères minimum
  - Au moins une majuscule, un chiffre, un caractère spécial
- Validation WTForms sur tous les champs d'entrée utilisateur

### 2. Protection CSRF

- `Flask-WTF CSRFProtect` activé globalement
- Token CSRF présent sur **tous** les formulaires POST
- Token inclus dans le formulaire de déconnexion (`/auth/logout`)
- Expiration du token : 1 heure

### 3. Gestion des sessions

- Durée de vie : **30 minutes** d'inactivité (`PERMANENT_SESSION_LIFETIME`)
- Cookie `HttpOnly` : inaccessible depuis JavaScript
- Cookie `SameSite=Lax` : protection contre le CSRF cross-origin
- Cookie `Secure` : activé en production (HTTPS uniquement)
- Invalidation complète de la session à la déconnexion

### 4. Contrôle d'accès (RBAC)

- 3 rôles : `admin`, `professor`, `student`
- Décorateurs serveur-side sur chaque route : `@admin_required`, `@professor_required`, `@student_required`
- Tout accès refusé (403) est **automatiquement journalisé** dans `audit_logs`
- Protection IDOR : les étudiants ne peuvent accéder qu'aux données qui leur appartiennent
  - `course_detail` vérifie l'existence d'une entrée `Grade` avant d'afficher
  - Un professeur ne peut modifier que ses propres cours (`course.professor.user_id`)

### 5. En-têtes de sécurité HTTP

Tous les en-têtes sont injectés via `@after_request` sur chaque réponse :

| En-tête | Valeur |
|---------|--------|
| `X-Frame-Options` | `DENY` — prévient le clickjacking |
| `X-Content-Type-Options` | `nosniff` — prévient le MIME sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` |
| `Content-Security-Policy` | `default-src 'self'` — prévient XSS et injection de ressources |

### 6. Requêtes paramétrées

- **Zéro SQL brut** dans le code applicatif
- Toutes les requêtes passent par l'ORM SQLAlchemy
- Prévient les injections SQL par conception

### 7. Journalisation (Audit Logs)

Chaque action sensible est enregistrée dans la table `audit_logs` :

- Connexion réussie / échouée
- Inscription / déconnexion
- Création, modification, suppression d'utilisateur
- Inscription / désinscription à un cours
- Attribution / modification d'une note
- Tentatives d'accès non autorisé (403)

Données enregistrées : `user_id`, `username`, `action`, `resource_type`, `resource_id`, `ip_address`, `timestamp`

### 8. Infrastructure

- Conteneur Docker avec utilisateur non-root (uid=1001, gid=1001)
- Image basée sur `python:3.11-slim` (surface d'attaque minimale)
- Secrets passés par variables d'environnement, jamais dans le code
- `SECRET_KEY` générée aléatoirement en production via la variable d'env

---

## Dépendances surveillées

Le pipeline CI/CD intègre `pip-audit` en mode strict : toute dépendance avec un CVE connu
bloque le déploiement.

Scan de sécurité statique (SAST) via **Bandit** à chaque push : les issues de sévérité HIGH
bloquent le pipeline.

Scan dynamique (DAST) via **OWASP ZAP** avant chaque déploiement en production.

---

## Versions des dépendances clés

| Paquet | Version | Rôle |
|--------|---------|------|
| Flask | 3.0.3 | Framework web |
| Flask-Bcrypt | 1.0.1 | Hachage passwords |
| Flask-WTF | 1.2.1 | CSRF + formulaires |
| cryptography | 43.0.1 | Primitives crypto |
| PyMySQL | 1.1.1 | Driver MySQL |
