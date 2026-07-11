# 🧮 Abacus

> **Comptabilité associative en partie double, conforme au règlement ANC 2018-06 — simple pour un bénévole, complète pour un expert-comptable.**

Abacus est une application web de **comptabilité associative**. Le trésorier saisit
une recette ou une dépense en langage clair ; en coulisses, le moteur transforme
chaque saisie en **écriture en partie double** sur un plan de comptes ANC. La
complexité comptable existe mais reste **masquée par défaut** (progressive
disclosure) : elle se révèle pour qui en a besoin (journal complet, saisie manuelle,
balance, grand livre, bilan, compte de résultat, exports FEC).

Abacus est un **SaaS multi-association** : chaque association est un tenant
**strictement isolé**, auquel des **comptes personnels** accèdent avec des **rôles
et des permissions fines** (RBAC).

---

## 📋 Table des matières

- [Présentation](#-présentation)
- [Fonctionnalités](#-fonctionnalités)
- [Technologies utilisées](#️-technologies-utilisées)
- [Installation](#-installation)
- [Lancement de l'application](#-lancement-de-lapplication)
- [Développement & Qualité](#-développement--qualité)
- [Sécurité](#-sécurité)
- [Serveur MCP](#-serveur-mcp)
- [Architecture](#️-architecture)
- [Licence](#-licence)

---

## 🎯 Présentation

**Deux niveaux de lecture, une seule application :**

- Le **trésorier bénévole** choisit un type d'opération (Recette / Dépense /
  Virement), un montant, une date et un compte. Il ne voit jamais « débit / crédit ».
- Le **moteur comptable** génère l'écriture en partie double conforme au plan de
  comptes associatif (ANC 2018-06).
- Le **trésorier aguerri / l'expert-comptable** accède au journal complet, à la
  saisie manuelle multi-lignes, au grand livre, à la balance, au bilan, au compte
  de résultat, à l'annexe et aux exports normés (PDF, Excel, **FEC**).

Principe directeur : **simple par défaut, puissant au besoin**. Une petite
association ne déplie jamais le volet « Avancé » ; un trésorier confirmé, oui.

---

## ⚡ Fonctionnalités

### 🧾 Saisie & journal
- **Saisie type-first** (Recette / Dépense / **Virement interne**) → écriture partie
  double automatique ; volet **Avancé** replié (catégorie, événement, tiers,
  justificatif, référence, mode de règlement).
- **Journal** complet : filtres riches multi-valeur (type, catégorie, tiers,
  événement, compte, dates, texte), tiroir de détail, **validation**, **édition** de
  brouillon, **contre-passation** et **annule-et-remplace** en un clic (immuabilité
  ANC préservée), actions groupées.
- **Justificatifs** : upload sécurisé (type sniffé par magic bytes, borné), aperçu
  inline sandboxé.

### 📊 Pilotage
- **Synthèse** : résultat/recettes/dépenses sur période réglable, répartition par
  catégorie et par événement, courbe de trésorerie, panneau d'alertes, widget budget.
- **Événements** : axe analytique transversal (budget prévu vs réalisé par action).
- **Budget** : prévu / réalisé par catégorie, annuel par exercice.

### 🏦 Trésorerie & récurrences
- **Comptes de trésorerie nommés** (banque / caisse / en ligne / épargne), soldes
  calculés depuis le grand livre, solde initial via écriture d'à-nouveau.
- **Banque** : import de relevés **CSV** (mapping de colonnes) et **OFX** (dédup
  FITID), rapprochement / lettrage avec suggestions.
- **Récurrences** : modèles récurrents (loyers, abonnements…) en mode proposition ou
  automatique, avec un scheduler quotidien à heure fixe configurable.

### 📑 États légaux & conformité (ANC 2018-06)
- **Exercices** : ouverture, **clôture** (détermination du résultat, report à nouveau,
  affectation), verrouillage des écritures clôturées.
- **Compte de résultat**, **bilan**, **annexe** (tableaux calculés + rubriques
  narratives éditables) — exports PDF.
- **Journal / grand livre / relevés** — exports PDF + Excel.
- **FEC** (Fichier des Écritures Comptables) conforme à l'arrêté du 29/07/2013.
- **TVA optionnelle** : masquée tant que le régime n'est pas activé.
- **Dons & reçus fiscaux Cerfa** conformes (art. 200 / 238 bis), par don ou annuel.

### 👥 Multi-association & rôles
- Comptes personnels **multi-associations** ; le rôle est porté par le lien
  user ↔ association (`Membership`).
- **RBAC fin** : rôles-presets (Trésorier / Expert-comptable / Lecture / Admin) +
  overrides de permissions par membre, **effectif calculé côté serveur**.
- **Invitations** signées et expirables ; **audit** métier cloisonné par tenant.

### 🤖 Intégration IA (MCP)
- Serveur **Model Context Protocol** à `/mcp` (Streamable HTTP, `X-API-Key`).
- Outils **filtrés par les permissions effectives** de la clé, écriture **assistée
  born-brouillon** (aucune validation / suppression / clôture via MCP).

---

## 🛠️ Technologies utilisées

### Frontend

| Technologie | Version | Rôle |
| :--- | :--- | :--- |
| [React](https://react.dev/) | 19.x | Framework UI |
| [TypeScript](https://www.typescriptlang.org/) | 5.x | Typage statique |
| [Vite](https://vitejs.dev/) | 6.x | Build & dev server |
| [TanStack Query](https://tanstack.com/query) | 5.x | État serveur & cache |
| [Tailwind CSS](https://tailwindcss.com/) | 4.x (CSS-first, tokens `@theme`) | Styles |
| [Recharts](https://recharts.org/) | 3.x | Graphiques (chargés en chunk lazy) |
| [Vitest](https://vitest.dev/) | 4.x | Tests unitaires |

Polices **IBM Plex Sans / Mono** self-hostées (`@fontsource`, CSP `font-src 'self'`).

### Backend

| Technologie | Rôle |
| :--- | :--- |
| [FastAPI](https://fastapi.tiangolo.com/) `0.139` | Framework API |
| [SQLModel](https://sqlmodel.tiangolo.com/) | ORM (SQLAlchemy + Pydantic) |
| [PostgreSQL](https://www.postgresql.org/) 16 | Base de données (prod) |
| [Alembic](https://alembic.sqlalchemy.org/) | Migrations |
| [argon2-cffi](https://argon2-cffi.readthedocs.io/) | Hachage des mots de passe |
| [slowapi](https://github.com/laurentS/slowapi) | Rate-limiting |
| [fpdf2](https://py-pdf.github.io/fpdf2/) + [openpyxl](https://openpyxl.readthedocs.io/) | Exports PDF / Excel |
| [ofxparse](https://github.com/jseutter/ofxparse) | Import de relevés OFX |
| [MCP SDK](https://modelcontextprotocol.io/) `1.23` | Serveur Model Context Protocol |
| [Pytest](https://docs.pytest.org/) · [Ruff](https://docs.astral.sh/ruff/) | Tests · lint/format |

---

## 📦 Installation

### Prérequis

- **Node.js** v20+
- **Python** v3.11+
- **PostgreSQL** v14+ (les tests peuvent tourner sur SQLite en mémoire)
- **Docker** & **Docker Compose** (pour le déploiement)

### 1️⃣ Cloner le projet

```bash
git clone <url-du-repo>
cd abacus
```

### 2️⃣ Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # ou venv\Scripts\activate sous Windows
pip install -r requirements.txt
cp .env.example .env            # configurez DATABASE_URL, SECRET_KEY, …
alembic upgrade head            # applique les migrations (chaîne 0001 → 0030)
```

### 3️⃣ Frontend

```bash
cd frontend
npm install
```

---

## 🚀 Lancement de l'application

### Mode développement

**Terminal 1 — Backend**

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API : `http://localhost:8000/docs`

**Terminal 2 — Frontend**

```bash
cd frontend
npm run dev
```

Application : `http://localhost:9873` (le proxy `/api` pointe vers `:8000`).

### Environnement de test (simulation de prod, en une commande)

Pour lancer **l'image de production** (frontend + backend dans un seul conteneur)
avec PostgreSQL, les migrations et un compte de démo, sans rien configurer :

```bash
./scripts/run-test.sh        # build + démarrage + données de démo
```

Puis ouvrez `http://localhost:8000` et connectez-vous :

- **e-mail** : `demo@abacus.test` · **mot de passe** : `demo-password-123`
- l'association « Association Démo » est déjà créée (plan comptable ANC seedé)

Cet environnement reflète la production (même image, migrations, en-têtes de
sécurité, CSP, argon2, vérif d'origine/CSRF). Deux réglages sont volontairement
relâchés pour rester joignable en `http://localhost` : `ENVIRONMENT=staging`
désactive le flag `Secure` des cookies et l'en-tête HSTS (tous deux exigent HTTPS).
La config tient dans `.env.test` (valeurs locales jetables, **jamais** pour la prod) ;
le projet Docker est isolé (`abacus-test`, volume dédié).

```bash
./scripts/run-test.sh logs    # logs de l'app en direct
./scripts/run-test.sh down    # arrêt (données conservées)
./scripts/run-test.sh reset   # arrêt + effacement de la base de test
./scripts/run-test.sh psql    # shell psql dans le conteneur db
```

### Mode production (Docker)

Le déploiement repose sur **Docker Compose** et **un unique conteneur applicatif**.
Une image multi-stage build le frontend (Node), puis FastAPI sert les fichiers
statiques (avec fallback SPA) **aux côtés de l'API et du serveur MCP, sur le même
port 8000**. Deux services tournent :

| Service | Rôle | Port |
| :--- | :--- | :--- |
| `db`  | PostgreSQL 16 (volume persistant `pgdata`) | interne |
| `app` | FastAPI : front + `/api` + `/mcp` | **8000** |

Les **migrations Alembic sont appliquées automatiquement** au démarrage du conteneur
`app` (`alembic upgrade head`).

#### 1️⃣ Configuration (`.env`)

```bash
cp .env.example .env
```

| Variable | Obligatoire | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | ✅ | `production` : impose un `SECRET_KEY` non-défaut et les cookies `Secure`. |
| `DATABASE_URL` | ✅ | URL PostgreSQL (`postgresql+psycopg://…`). |
| `SECRET_KEY` | ✅ | Clé de signature des JWT. **L'app refuse de démarrer en production avec la valeur par défaut.** Générez-la : `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `CORS_ORIGINS` | ✅ | URL(s) publiques autorisées (séparées par virgule). **Si absente, toutes les écritures (POST/PUT/PATCH/DELETE) sont rejetées en 403** — un warning est loggé au démarrage. |
| `APP_URL` | ✅ | URL publique (liens des e-mails d'invitation). |
| `LOGS_USER` / `LOGS_PASS` | ✅ | Identifiants HTTP Basic de la vue technique globale des logs (`/api/logs`). |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | Durée de l'access token (défaut 15). |
| `REFRESH_TOKEN_EXPIRE_DAYS` | — | Durée du refresh token (défaut 30). |
| `AUTH_RATE_LIMIT` | — | Limite sur register / login / accept (défaut `5/minute`). |
| `LOG_RETENTION_DAYS` | — | Purge des logs plus vieux que N jours (défaut 90, `0` désactive). |
| `SMTP_*` | — | SMTP pour les e-mails d'invitation (sinon le lien est renvoyé/loggé). |

Réglages avancés facultatifs (valeurs par défaut saines) : `RECURRENCE_HOUR` /
`RECURRENCE_TZ` (heure du scheduler, défaut 06:00 Europe/Paris), `MCP_RATE_LIMIT` /
`MCP_RATE_WINDOW` (throttle du transport `/mcp`), `STORAGE_DIR` (justificatifs).

#### 2️⃣ Déploiement via Docker Compose (serveur manuel)

```bash
git clone <url-du-repo> && cd abacus
cp .env.example .env        # éditez les valeurs ci-dessus
docker compose up --build -d
```

L'application écoute sur le port `8000` du conteneur `app`. Vérifiez la santé :

```bash
curl http://localhost:8000/health   # -> {"status":"ok"}
```

Placez un reverse proxy (Nginx, Caddy, Traefik…) devant `app:8000` pour le domaine
et le TLS — **aucun routage de chemins n'est nécessaire**, le service sert déjà le
front et l'API ensemble.

#### 3️⃣ Déploiement via Coolify (recommandé)

1. Créez une ressource **Docker Compose** pointant sur ce dépôt.
2. Renseignez les **variables d'environnement** (mêmes que le `.env` ci-dessus).
3. Attachez votre **domaine au service `app` (port 8000)** ; Coolify gère le domaine
   et le TLS (aucun reverse proxy ni routage `/api` / `/mcp` à définir).
4. Mettez `CORS_ORIGINS` et `APP_URL` à votre **URL publique**.

#### ✅ Checklist post-déploiement

- [ ] `SECRET_KEY` défini (sinon l'app refuse de démarrer en production)
- [ ] `CORS_ORIGINS` = URL publique (sinon 403 sur toutes les écritures)
- [ ] `GET /health` renvoie `{"status":"ok"}`
- [ ] Création de compte / d'association et saisie d'une opération fonctionnelles
- [ ] Identifiants `LOGS_USER` / `LOGS_PASS` changés

#### 🛑 Arrêt, sauvegarde et mise à jour (sans perdre les données)

Les données vivent dans le **volume Docker nommé `pgdata`**, indépendant des
conteneurs. Arrêter ou recréer les conteneurs ne supprime **pas** ce volume.

```bash
# Arrêt en conservant les données
docker compose stop          # arrête les conteneurs, tout est conservé
docker compose down          # supprime les conteneurs MAIS conserve le volume pgdata

# Redémarrage / mise à jour (données conservées)
git pull && docker compose up --build -d   # les migrations s'appliquent au démarrage
```

> ⚠️ **Ne jamais utiliser `docker compose down -v` en production** : le flag `-v`
> **supprime le volume `pgdata` et détruit toutes les données**.

**Sauvegarde / restauration** (recommandé avant toute maintenance) :

```bash
# Sauvegarde (dump SQL horodaté)
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup_$(date +%F).sql

# Restauration dans une base vide
cat backup_AAAA-MM-JJ.sql | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

> Sous **Coolify** : « Stop » et les redéploiements conservent le volume. Ne
> supprimez la ressource (ou son volume) que pour effacer les données — faites un
> `pg_dump` au préalable. Coolify permet aussi de planifier des sauvegardes.

---

## 🧪 Développement & Qualité

Le projet suit des standards stricts : **TDD** (test d'abord), isolation tenant
testée systématiquement, revues de sécurité (`semgrep ci`), commits atomiques.

### Frontend

```bash
cd frontend
npm run lint     # ESLint (--max-warnings 0)
npm run test     # Vitest
npm run build    # tsc + vite build
```

### Backend

```bash
cd backend
./venv/bin/ruff check . && ./venv/bin/ruff format --check .
./venv/bin/python -m pytest -q
```

> Les tests utilisent SQLite en mémoire par défaut (rapide). La CI vise PostgreSQL
> via `TEST_DATABASE_URL` (divergences Decimal / datetime / FK) et valide les
> migrations (`alembic upgrade head` sur base vide).

---

## 🔐 Sécurité

Priorité n°1, avec des comptes accédant à **plusieurs associations** :

- **Zéro confiance sur les entrées** : validation et autorisation **toujours côté
  serveur** ; tout objet chargé par un id client passe par le helper tenant-scopé
  `owned_or_404` (pas de fuite d'existence).
- **Isolation multi-tenant** : chaque requête re-vérifie le `Membership` de l'asso
  active ; toute entité porte un `association_id` filtré en `AND`.
- **RBAC** : permissions vérifiées sur chaque route (jamais seulement masquées dans
  l'UI), effectif = preset(rôle) ± overrides, calculé serveur.
- **Auth** : mots de passe **argon2id** (rehash transparent), cookies **HttpOnly** +
  `SameSite` (+ `Secure` en prod), access token court + refresh rotatif **révocable**,
  protection **CSRF** par validation d'origine, en-têtes **CSP / HSTS**.
- **Anti-abus** : rate-limiting (register / login / refresh / accept), **lockout de
  compte** après échecs répétés, throttle du transport `/mcp`.
- **Intégrité comptable** : écritures validées **immuables**, exercices clôturés
  **verrouillés**, numérotation de pièces **séquentielle sans trou** (FEC), correction
  par **contre-passation** (jamais d'édition silencieuse).

---

## 🤖 Serveur MCP

Abacus expose un serveur [Model Context Protocol](https://modelcontextprotocol.io/)
permettant à un agent IA de consulter et d'alimenter la comptabilité d'une
association, **dans la limite des permissions de la clé API**.

### Configuration

1. Créez une clé API depuis **Paramètres → Clés API / MCP** (le secret `abk_…`
   n'est affiché qu'une fois). La clé est liée à un membre : elle hérite de ses
   permissions effectives.
2. Ajoutez cette configuration à votre client MCP (Claude Desktop, Claude Code, …) :

```json
{
  "mcpServers": {
    "abacus": {
      "type": "streamable-http",
      "url": "https://votre-serveur.com/mcp",
      "headers": { "X-API-Key": "abk_..." }
    }
  }
}
```

### Outils disponibles

**Lecture** (filtrés par les permissions de la clé) :
`get_synthese`, `list_ecritures`, `balance_comptes`, `grand_livre`,
`compte_resultat`, `bilan`, `list_dons`, `list_comptes`,
`list_comptes_tresorerie`, `list_categories`.

**Écriture assistée** (créent toujours un **brouillon**, jamais validé) :
`saisir_recette`, `saisir_depense`, `creer_tiers`.

> Garde-fous : aucun outil de validation, de suppression d'écriture ou de clôture
> n'est exposé — un humain valide toujours dans l'application. Chaque appel
> re-vérifie la permission côté serveur et journalise les écritures.

---

## 🏗️ Architecture

```
abacus/
├── frontend/                # Application React
│   └── src/
│       ├── pages/           # Synthèse, Saisie, Journal, Banque, Budget, Dons,
│       │                    #   Récurrences, Rapports, Paramètres, onboarding…
│       ├── components/      # Composants par domaine (journal, synthese, saisie…)
│       ├── api/             # Couche API typée (package accounting/ + clients)
│       ├── hooks/ · lib/    # Hooks (permissions, filtres) · utilitaires partagés
│       └── ...
├── backend/                 # API FastAPI
│   ├── routers/             # Endpoints par domaine (ecritures, banque, budget,
│   │                        #   exercices, recus, permissions, annexe, apikeys…)
│   ├── accounting_engine/   # Moteur partie double (invariants, builders, clôture…)
│   ├── exports/             # Génération PDF (fpdf2) / Excel (openpyxl) / FEC
│   ├── mcp_server/          # Serveur MCP v2 (tools, dispatch, handlers)
│   ├── models/              # Modèles de données par domaine
│   ├── alembic/versions/    # Migrations (chaîne 0001 → 0030)
│   ├── auth_context.py      # Isolation tenant (get_active_membership, owned_or_404)
│   ├── authz.py             # Matrice RBAC & permissions effectives
│   ├── main.py              # Point d'entrée FastAPI + montage MCP + statiques
│   └── tests/               # Tests d'intégration et unitaires
├── docker-compose.yml       # db (PostgreSQL) + app (front + API + MCP)
└── scripts/run-test.sh      # Simulation de production en une commande
```

---

## 📄 Licence

Ce projet est sous licence **[EUROPEAN UNION PUBLIC LICENCE v. 1.2](https://eupl.eu/1.2/en/)**.

**Auteur** : Coodlab — Mallevaey Lino
**Version** : 2026.07.12
</content>
</invoke>
