# 🧮 Abacus

> **Application de comptabilité simplifiée pour associations**

Abacus est une application web moderne conçue spécifiquement pour la gestion comptable des associations. Elle offre une interface intuitive et élégante permettant de gérer facilement vos balances financières, d'enregistrer vos opérations et de visualiser vos données comptables en temps réel.

---

## 📋 Table des matières

- [Présentation](#-présentation)
- [Fonctionnalités](#-fonctionnalités)
- [Technologies utilisées](#️-technologies-utilisées)
- [Installation](#-installation)
- [Lancement de l'application](#-lancement-de-lapplication)
- [Développement & Qualité](#-développement--qualité)
- [Architecture](#-architecture)
- [Licence](#-licence)

---

## 🎯 Présentation

**Abacus** est née du besoin de simplifier la comptabilité associative. Au lieu de jongler avec des tableurs complexes, Abacus propose une solution web tout-en-un qui centralise :

- ✅ **La gestion de vos balances** (compte principal, caisse, épargne, etc.)
- ✅ **L'enregistrement de vos opérations** (recettes et dépenses)
- ✅ **La visualisation de vos données** avec des graphiques interactifs
- ✅ **L'export PDF** de vos rapports financiers
- ✅ **La sécurité** avec un système d'authentification robuste (Cookies HttpOnly)
- ✅ **Le multi-tenant** pour gérer plusieurs associations sur une même instance

L'application a été pensée pour être **minimaliste**, **rapide** et **accessible**, même pour les utilisateurs non techniques.

---

## ⚡ Fonctionnalités

### 🏠 Dashboard interactif

- Vue d'ensemble de votre santé financière
- Affichage en carrousel de toutes vos balances
- Graphiques d'évolution des revenus et dépenses
- Tableaux détaillés de toutes les opérations

### 💰 Gestion des balances

- Création et suppression de balances multiples
- Modification du nom et du montant initial
- Suivi du solde actuel en temps réel
- Organisation par cartes visuelles avec Drag & Drop

### 📊 Gestion des opérations

- Enregistrement de recettes et dépenses
- Catégorisation des opérations (salaires, achats, dons, etc.)
- Ajout de descriptions détaillées
- Modification et suppression intuitives

### 📈 Visualisations

- **Graphiques** : Évolution temporelle avec Recharts
- **Tableaux** : Liste détaillée et filtrable de toutes les opérations
- **Carrousel** : Navigation fluide entre vos différentes balances

### 📄 Export PDF

- Génération de rapports PDF professionnels
- Consolidation de toutes les opérations par période
- Une page par balance avec design soigné
- Export direct depuis le dashboard

### 🔐 Sécurité

- Authentification sécurisée via Cookies **HttpOnly** (Protection XSS)
- Hachage sécurisé des mots de passe (bcrypt)
- Isolation stricte des données entre associations

---

## 🛠️ Technologies utilisées

### **Frontend**

| Technologie | Version | Description |
| :--- | :--- | :--- |
| [React](https://react.dev/) | 19.x | Framework UI moderne |
| [TypeScript](https://www.typescriptlang.org/) | 5.x | JavaScript typé pour plus de robustesse |
| [Vite](https://vitejs.dev/) | 6.x | Build tool ultra-rapide |
| [TanStack Query](https://tanstack.com/query) | 5.x | Gestion d'état serveur et cache |
| [Tailwind CSS](https://tailwindcss.com/) | 3.x | Framework CSS utilitaire |
| [Recharts](https://recharts.org/) | 3.x | Bibliothèque de graphiques React |
| [Vitest](https://vitest.dev/) | 1.x | Framework de test unitaire rapide |

### **Backend**

| Technologie | Description |
| :--- | :--- |
| [FastAPI](https://fastapi.tiangolo.com/) | Framework Python moderne et performant |
| [SQLModel](https://sqlmodel.tiangolo.com/) | ORM basé sur SQLAlchemy et Pydantic |
| [MySQL](https://www.mysql.com/) | Base de données relationnelle |
| [Pytest](https://docs.pytest.org/) | Framework de test Python standard |
| [Ruff](https://docs.astral.sh/ruff/) | Linter et Formatter Python ultra-rapide |

---

## 📦 Installation

### Prérequis

- **Node.js** (v18 ou supérieur)
- **Python** (v3.11 ou supérieur)
- **MySQL** (ou MariaDB)

### 1️⃣ Cloner le projet

```bash
git clone <url-du-repo>
cd abacus
```

### 2️⃣ Configuration du Backend

1.  **Installer les dépendances** :
    ```bash
    cd backend
    python -m venv venv
    source venv/bin/activate  # Ou venv\Scripts\activate sous Windows
    pip install -r requirements.txt
    ```

2.  **Configuration** :
    Copiez `.env.example` vers `.env` et configurez votre base de données et votre clé secrète.
    ```bash
    cp .env.example .env
    ```

3.  **Initialiser la base de données** :
    ```bash
    python cli.py setup-db
    ```

### 3️⃣ Configuration du Frontend

```bash
# À la racine du projet
npm install
```

---

## 🚀 Lancement de l'application

### Mode développement

#### Terminal 1 : Backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
API : `http://localhost:8000/docs`

#### Terminal 2 : Frontend

```bash
npm run dev
```
Application : `http://localhost:9873`

### Mode production (Docker)

Le moyen le plus simple de lancer en production est d'utiliser Docker Compose :

```bash
docker-compose up --build -d
```
L'application sera accessible sur le port **9874**.

---

## 🧪 Développement & Qualité

Le projet suit des standards de qualité stricts.

### Frontend

- **Linting** : `npm run lint` (ESLint)
- **Formatage** : `npm run format` (Prettier)
- **Tests** : `npm run test` (Vitest)
- **Build** : `npm run build` (TypeScript + Vite)

### Backend

- **Linting & Formatage** : `ruff check .` et `ruff format .`
- **Tests** : `pytest`

---

## 🏗️ Architecture

```
abacus/
├── src/                  # Code source Frontend
│   ├── components/       # Composants React (atomiques et métier)
│   │   └── dashboard/    # Sous-composants du Dashboard
│   ├── hooks/            # Hooks personnalisés (React Query)
│   ├── api.ts            # Couche API typée
│   ├── types.ts          # Définitions TypeScript partagées
│   └── ...
├── backend/              # Code source Backend
│   ├── routers/          # Endpoints API découpés par domaine
│   ├── models.py         # Modèles de données (DB & Pydantic)
│   ├── security.py       # Logique d'authentification
│   ├── main.py           # Point d'entrée FastAPI
│   └── tests/            # Tests d'intégration et unitaires
├── public/               # Assets statiques
└── ...
```

---

## 📄 Licence

Ce projet est sous licence **CC BY-NC-SA 4.0**.

**Auteur** : Coodlab, Mallevaey Lino  
**Version** : 2025.11.22