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
- [Utilisation](#-utilisation)
- [Commandes CLI](#️-commandes-cli)
- [Architecture](#-architecture)
- [Licence](#-licence)

---

## 🎯 Présentation

**Abacus** est née du besoin de simplifier la comptabilité associative. Au lieu de jongler avec des tableurs complexes, Abacus propose une solution web tout-en-un qui centralise :

- ✅ **La gestion de vos balances** (compte principal, caisse, épargne, etc.)
- ✅ **L'enregistrement de vos opérations** (recettes et dépenses)
- ✅ **La visualisation de vos données** avec des graphiques interactifs
- ✅ **L'export PDF** de vos rapports financiers
- ✅ **La sécurité** avec un système d'authentification utilisateur
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
- Organisation par cartes visuelles

### 📊 Gestion des opérations

- Enregistrement de recettes et dépenses
- Catégorisation des opérations (salaires, achats, dons, etc.)
- Ajout de descriptions détaillées
- Menu contextuel pour éditer ou supprimer
- Modal de confirmation pour les suppressions

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

- Authentification par utilisateur (login/password)
- Hachage sécurisé des mots de passe (bcrypt)
- Isolation multi-tenant des données
- Sessions sécurisées

---

## 🛠️ Technologies utilisées

### **Frontend**

| Technologie                                   | Version | Description                             |
| --------------------------------------------- | ------- | --------------------------------------- |
| [React](https://react.dev/)                   | 19.2.0  | Framework UI moderne et performant      |
| [TypeScript](https://www.typescriptlang.org/) | 5.8.2   | JavaScript typé pour plus de robustesse |
| [Vite](https://vitejs.dev/)                   | 6.2.0   | Build tool ultra-rapide                 |
| [Tailwind CSS](https://tailwindcss.com/)      | -       | Framework CSS utilitaire                |
| [Recharts](https://recharts.org/)             | 3.3.0   | Bibliothèque de graphiques React        |
| [React PDF](https://react-pdf.org/)           | 4.3.1   | Génération de documents PDF             |
| [date-fns](https://date-fns.org/)             | 4.1.0   | Manipulation de dates                   |

### **Backend**

| Technologie                                | Description                                |
| ------------------------------------------ | ------------------------------------------ |
| [FastAPI](https://fastapi.tiangolo.com/)   | Framework Python moderne et performant     |
| [SQLModel](https://sqlmodel.tiangolo.com/) | ORM basé sur SQLAlchemy et Pydantic        |
| [MySQL](https://www.mysql.com/)            | Base de données relationnelle              |
| [PyMySQL](https://pymysql.readthedocs.io/) | Connecteur MySQL pour Python               |
| [Uvicorn](https://www.uvicorn.org/)        | Serveur ASGI haute performance             |
| [Typer](https://typer.tiangolo.com/)       | CLI moderne pour Python                    |
| [Rich](https://github.com/Textualize/rich) | Rendu de texte enrichi dans le terminal    |
| [Passlib](https://passlib.readthedocs.io/) | Hachage sécurisé de mots de passe (bcrypt) |

---

## 📦 Installation

### Prérequis

Avant de commencer, assurez-vous d'avoir installé :

- **Node.js** (v16 ou supérieur) - [Télécharger](https://nodejs.org/)
- **Python** (v3.8 ou supérieur) - [Télécharger](https://www.python.org/)
- **MySQL** (v5.7 ou supérieur) - [Télécharger](https://www.mysql.com/)

### 1️⃣ Cloner le projet

```bash
git clone <url-du-repo>
cd abacus
```

### 2️⃣ Configuration du Backend

#### Installer les dépendances Python

```bash
cd backend
pip install -r requirements.txt
```

> **Note** : Il est recommandé d'utiliser un environnement virtuel :
>
> ```bash
> python -m venv venv
> # Windows
> venv\Scripts\activate
> # Linux/Mac
> source venv/bin/activate
> ```

#### Configurer la base de données

1. **Créer une base de données MySQL** :

   ```sql
   CREATE DATABASE abacus CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

2. **Configurer les variables d'environnement** :
   - Copier le fichier d'exemple :
     ```bash
     # Linux/Mac
     cp .env.example .env
     # Windows
     copy .env.example .env
     ```
   - Éditer le fichier `.env` et renseigner vos informations MySQL :
     ```env
     DATABASE_URL=mysql+pymysql://utilisateur:motdepasse@localhost:3306/abacus
     ```
     > Remplacez `utilisateur`, `motdepasse` et `localhost:3306` par vos paramètres MySQL.

3. **Initialiser les tables** :
   ```bash
   python cli.py setup-db
   ```

### 3️⃣ Configuration du Frontend

#### Installer les dépendances Node.js

Depuis la racine du projet :

```bash
npm install
```

---

## 🚀 Lancement de l'application

### Mode développement

Pour développer avec rechargement automatique, lancez le backend et le frontend dans **deux terminaux séparés** :

#### Terminal 1 : Backend

```bash
cd backend
python cli.py start
```

✅ Le backend sera accessible sur **http://localhost:8000**

- API REST : `http://localhost:8000/api`
- Documentation Swagger : `http://localhost:8000/docs`

#### Terminal 2 : Frontend

```bash
npm run dev
```

✅ L'application sera accessible sur **http://localhost:9873**

### Mode production

Pour lancer l'application complète en production :

```bash
python run_prod.py
```

✅ L'application sera accessible sur **http://0.0.0.0:9874**

Ce script :

1. Compile le frontend React en version optimisée
2. Copie les fichiers statiques dans le dossier `backend`
3. Lance le serveur FastAPI en mode production

---

## 📖 Utilisation

### 1. Première connexion

1. Ouvrez votre navigateur sur `http://localhost:9873` (dev) ou `http://localhost:9874` (prod)
2. **Créez un compte** en cliquant sur "Register"
3. Remplissez vos informations (nom d'utilisateur et mot de passe)
4. Connectez-vous avec vos identifiants

### 2. Créer votre première balance

1. Sur le dashboard, cliquez sur le bouton **"+ Ajouter une balance"**
2. Remplissez les informations :
   - **Nom** : ex. "Compte Principal", "Caisse", "Épargne"
   - **Montant initial** : le solde de départ (peut être 0)
3. Validez

### 3. Ajouter des opérations

1. Sélectionnez une balance dans le carrousel
2. Cliquez sur **"+ Ajouter une opération"**
3. Renseignez les détails :
   - **Type** : Recette ou Dépense
   - **Montant** : montant de l'opération
   - **Date** : date de l'opération
   - **Catégorie** : type d'opération (salaire, achat, don, etc.)
   - **Description** : détails complémentaires
4. Validez

### 4. Visualiser vos données

- **Carrousel** : Naviguez entre vos balances avec les flèches
- **Graphiques** : Consultez l'évolution de vos revenus/dépenses au fil du temps
- **Tableau** : Visualisez toutes les opérations en détail, triables et filtrables

### 5. Modifier ou supprimer

- **Opérations** : Clic droit sur une opération → Modifier ou Supprimer
- **Balances** : Menu contextuel sur chaque carte de balance

### 6. Exporter en PDF

1. Cliquez sur le bouton **"Exporter PDF"** dans l'en-tête
2. Le rapport complet sera généré et téléchargé automatiquement
3. Le PDF contient toutes vos balances et opérations avec un design professionnel

---

## 🎛️ Commandes CLI

Le backend dispose d'un outil CLI (`cli.py`) pour faciliter les tâches courantes :

| Commande                 | Description                                                                 |
| ------------------------ | --------------------------------------------------------------------------- |
| `python cli.py start`    | Démarre le serveur de développement FastAPI (avec rechargement automatique) |
| `python cli.py setup-db` | Crée toutes les tables nécessaires dans la base de données                  |
| `python cli.py reset-db` | ⚠️ **DANGER** : Supprime et recrée toutes les tables (perte de données)     |

**Exemples** :

```bash
# Démarrer le serveur
python cli.py start

# Créer les tables (première installation)
python cli.py setup-db

# Réinitialiser complètement la base (développement uniquement)
python cli.py reset-db
```

---

## 🏗️ Architecture

```
abacus/
├── backend/              # Backend FastAPI
│   ├── api/             # Routes API
│   ├── models/          # Modèles SQLModel
│   ├── database.py      # Configuration DB
│   ├── cli.py           # Outil CLI
│   ├── .env             # Variables d'environnement
│   └── requirements.txt # Dépendances Python
│
├── components/          # Composants React
│   ├── Dashboard.tsx
│   ├── BalanceCard.tsx
│   ├── OperationsTable.tsx
│   ├── OperationsChart.tsx
│   ├── AddBalanceModal.tsx
│   ├── AddOperationModal.tsx
│   ├── ExportButton.tsx
│   ├── PDFDocument.tsx
│   └── ...
│
├── public/              # Ressources statiques
├── App.tsx              # Composant principal
├── api.ts               # Client API
├── types.ts             # Types TypeScript
├── index.tsx            # Point d'entrée React
├── vite.config.ts       # Configuration Vite
├── package.json         # Dépendances Node.js
└── README.md            # Ce fichier
```

### Flux de données

1. **Frontend** (React) → HTTP Request → **Backend** (FastAPI)
2. **Backend** → SQL Query → **Database** (MySQL)
3. **Database** → Data → **Backend** → JSON Response → **Frontend**

### Multi-tenant

Chaque utilisateur a ses propres données isolées. Le backend filtre automatiquement toutes les requêtes en fonction de l'utilisateur connecté.

---

## 📄 Licence

Ce projet est sous licence **CC BY-NC-SA 4.0** (Creative Commons Attribution - Pas d'Utilisation Commerciale - Partage dans les Mêmes Conditions).

**Auteur** : Coodlab, Mallevaey Lino  
**Version** : 2025.11.22

---

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :

- Signaler des bugs
- Proposer de nouvelles fonctionnalités
- Soumettre des pull requests

---

## 📞 Support

Pour toute question ou problème :

- Ouvrez une issue sur le dépôt GitHub
- Consultez la documentation Swagger : `http://localhost:8000/docs`

---

<div align="center">

**Fait avec ❤️ pour simplifier la comptabilité associative**

</div>
