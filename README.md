# 🤖 Memecoin Bot — Détecteur Early Solana

Bot Telegram de détection précoce de memecoins à fort potentiel (x3–x5) sur la blockchain **Solana**, en utilisant **DexScreener** pour les données de marché et **GoPlus Security** pour l'analyse de sécurité on-chain.

---

## 📁 Structure du Projet

```
memecoin_bot/
├── main.py           → Boucle principale, scan, tracker, messages Telegram
├── config.py         → Tous les seuils de filtrage et paramètres
├── dexscreener.py    → Intégration API DexScreener (nouvelles paires, prix)
├── goplus.py         → Intégration API GoPlus Security (analyse Solana)
├── filters.py        → Moteur de scoring et évaluation des tokens
├── tracker.py        → Suivi post-alerte (x2, x3, x5, take profit)
├── database.py       → Base SQLite (déduplication, historique)
├── requirements.txt  → Dépendances Python
└── .env.example      → Template de configuration
```

---

## ⚙️ Installation

### 1. Cloner et préparer l'environnement

```bash
git clone <votre-repo>
cd memecoin_bot
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

### 2. Configurer le fichier `.env`

```bash
cp .env.example .env
```

Editez le fichier `.env` :

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
GOPLUS_API_KEY=                          # Laisser vide pour la version gratuite
```

**Comment obtenir votre Bot Token :**
1. Ouvrez Telegram et cherchez `@BotFather`
2. Envoyez `/newbot` et suivez les instructions
3. Copiez le token fourni dans `TELEGRAM_BOT_TOKEN`

**Comment obtenir votre Chat ID :**
1. Cherchez `@userinfobot` sur Telegram
2. Envoyez `/start`
3. Copiez l'ID affiché dans `TELEGRAM_CHAT_ID`

### 3. Lancer le bot

```bash
python main.py
```

---

## 🔧 APIs Utilisées

### DexScreener API (gratuite, sans clé)
| Endpoint | Usage |
|---|---|
| `GET /token-profiles/latest/v1` | Récupère les derniers tokens listés sur Solana |
| `GET /token-pairs/v1/solana/{address}` | Récupère les paires de trading d'un token |
| `GET /latest/dex/pairs/solana/{pairId}` | Données temps réel d'une paire (suivi post-alerte) |

**Rate limit :** 60 requêtes/minute — le bot poll toutes les 60 secondes.

### GoPlus Security API (gratuite jusqu'à 3 000 req/jour)
| Endpoint | Usage |
|---|---|
| `GET /api/v1/solana/token_security?contract_addresses={address}` | Analyse de sécurité complète du token SPL |

**Champs vérifiés :** honeypot, mint authority, freeze authority, top10 holders, dev wallet %, LP lock, buy/sell tax, holder count.

---

## 🎯 Critères de Filtrage

### Seuils de Marché
| Critère | Éliminatoire 🔴 | Modéré 🟡 | Fort 🟢 |
|---|---|---|---|
| Âge | < 20 min ou > 6h | 20–30 min ou 3–6h | 30 min – 3h |
| Liquidité | < $15K ou > $500K | $15K–$20K | $20K–$150K |
| Market Cap | < $30K ou > $1.5M | $700K–$1.5M | $30K–$700K |
| Volume 1h | < $5 000 | — | ≥ $5 000 |
| Vol/Liq ratio | < 0.1 | 0.3–0.6 | ≥ 0.6 |
| Transactions 1h | < 30 | — | ≥ 30 |
| Buy/Sell ratio | < 1.0 | 1.0–1.5 | ≥ 1.5 |

### Seuils de Sécurité (GoPlus)
| Critère | Résultat |
|---|---|
| Honeypot | Éliminatoire si positif |
| Mint authority active | Éliminatoire |
| Freeze authority active | Éliminatoire |
| Top 10 holders > 30% | Éliminatoire |
| LP non verrouillée | Éliminatoire |
| Buy/Sell tax > 10% | Éliminatoire |

### Score Final
- 🟢 **SIGNAL FORT** : ≥ 7 critères verts + aucun flag rouge
- 🟡 **SIGNAL MODÉRÉ** : ≥ 5 critères verts + aucun flag rouge
- 🔴 **ÉLIMINÉ** : 1 flag rouge suffit

---

## 📡 Suivi Post-Alerte

Dès qu'un token est alerté, le bot suit son prix toutes les **2 minutes** pendant **48 heures** et notifie automatiquement :

| Événement | Déclencheur |
|---|---|
| 🚀 **x2 atteint** | Prix = 2× le prix d'alerte |
| 🚀🚀 **x3 atteint** | Prix = 3× le prix d'alerte |
| 🚀🚀 **x5 atteint** | Prix = 5× le prix d'alerte |
| ⚠️ **Take Profit Warning** | Chute de 30% depuis le dernier palier atteint |

---

## 🗄️ Base de Données SQLite

Le bot crée automatiquement `memecoin_bot.db` avec deux tables :

- **`alerted_tokens`** : historique de tous les tokens alertés, leur prix de référence, et leur statut de suivi
- **`scan_history`** : statistiques de chaque scan (nombre de paires, signaux émis)

Ces données permettent d'analyser les performances du bot et d'affiner les seuils au fil du temps.

---

## 🔄 Ajuster les Seuils

Tous les seuils sont centralisés dans `config.py`. Exemple pour baisser le seuil de liquidité minimum :

```python
FILTERS = {
    "liquidity_min": 10_000,   # Était 15 000, baissé à 10 000
    ...
}
```

Redémarrez le bot après chaque modification.

---

## 🚀 Déploiement sur VPS (recommandé)

Pour que le bot tourne en continu, déployez-le sur un VPS Linux (DigitalOcean, Hetzner, etc.) avec `screen` ou `systemd` :

```bash
# Avec screen
screen -S memecoin_bot
python main.py
# Ctrl+A puis D pour détacher

# Ou avec systemd — créez /etc/systemd/system/memecoin_bot.service
```

---

## ⚠️ Avertissement

Ce bot est un outil d'aide à la décision. Les memecoins sont des actifs extrêmement volatils et spéculatifs. Aucun filtre ne garantit un gain. Utilisez ce bot de manière responsable et n'investissez que ce que vous êtes prêt à perdre.

---

## 📄 Licence

MIT — Utilisation libre, à vos risques et périls.
