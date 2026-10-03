# 📚 BiblioBot Paris — Assistant Telegram

> Assistant conversationnel intelligent pour les **Bibliothèques de la Ville de Paris**, propulsé par **Google Gemini 2.5 Flash** et connecté au portail Syracuse via [`parisbibpy`](https://github.com/botalla/parisbibpy).

Déployé sur **Google Cloud Run** en mode serverless (100% éligible au Free Tier GCP — $0.00/mois).

---

## ✨ Fonctionnalités Clés

- **💬 Dialogue en Langage Naturel** : Posez vos questions comme à un proche (*"Qu'est-ce qu'on doit rendre aujourd'hui ?"*, *"Prolonge la BD de Camille"*).
- **👨‍👩‍👧 Multi-Cartes & Famille** : Visualisation unifiée de toutes les cartes associées (`UserPairings`) sans jongler entre les comptes.
- **🎒 Trip Planner** : Regroupement automatique des retours par bibliothèque ordonnés par urgence pour préparer votre sac de sortie.
- **⚡ Prolongation en 1 Clic** : Prolongation unitaire ou en lot de tous les documents arrivant à échéance.
- **🖼️ Album de Couvertures** : Récupération des visuels de couvertures pour retrouver facilement les livres éparpillés dans la maison.
- **🛡️ Sécurité & Moindre Privilège** : Whitelist stricte d'utilisateurs Telegram, vérification du secret Webhook et gestion des secrets dans **GCP Secret Manager**.

---

## 🏛️ Architecture & Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) : Conception technique complète, schémas Mermaid et choix serverless.
- [USE_CASES.md](USE_CASES.md) : Spécification détaillée des 6 cas d'usage utilisateurs et commandes Telegram.
- [DEPLOYMENT.md](DEPLOYMENT.md) : Guide pas-à-pas pour l'infrastructure GCP et le pipeline CI/CD GitHub Actions.

---

## 🚀 Démarrage Rapide en Local

### 1. Cloner et installer les dépendances
```bash
git clone https://github.com/botalla/telegram-bib-bot.git
cd telegram-bib-bot

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Sur Windows: .venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt
```

### 2. Configuration des variables d'environnement
Copiez le modèle `.env.example` en `.env` :
```bash
cp .env.example .env
```
Renseignez vos identifiants :
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `ALLOWED_USER_IDS`
- `GEMINI_API_KEY`
- `PARISBIB_USERNAME` & `PARISBIB_PASSWORD`

### 3. Lancer le serveur local
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

---

## 🧪 Tests Unitaires & Linting

```bash
# Lancer la suite de tests unitaires
pytest -v tests/

# Vérifier la qualité du code
ruff check .
```

---

## 📦 Structure du Répertoire

```text
telegram-bib-bot/
├── .github/workflows/deploy.yml # Pipeline CI/CD GitHub Actions
├── Dockerfile                   # Image multi-stage non-root Python 3.11-slim
├── requirements.txt             # Dépendances applicatives et dev
├── pyproject.toml               # Configuration projet et outillage
├── scripts/
│   ├── set_webhook.py           # Gestion CLI du Webhook Telegram
│   └── setup_infra.sh           # Initialisation de l'infrastructure GCP
├── src/
│   ├── config.py                # Configuration Pydantic Settings
│   ├── main.py                  # Point d'entrée FastAPI & Webhook
│   ├── bot/
│   │   ├── dispatcher.py        # Routeur et middleware de sécurité
│   │   ├── handlers.py          # Commandes et callbacks Telegram
│   │   ├── keyboards.py         # Claviers interactifs Inline
│   │   └── formatters.py        # Formatage HTML et badges d'urgence
│   ├── ai/
│   │   ├── gemini_agent.py      # Client Gemini 2.5 Flash & Function Calling
│   │   └── tools_schema.py      # Déclaration des outils OpenAPI/Gemini
│   └── services/
│       ├── bib_service.py       # Wrapper métier autour de parisbibpy
│       └── session_store.py     # Cache de cookies (GCS en prod, local en dev)
└── tests/                       # Suite de tests unitaires et mocks
```
