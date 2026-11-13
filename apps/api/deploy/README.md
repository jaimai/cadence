# Déployer l'API sur alwaysdata

L'API et le worker tournent sur alwaysdata, la base sur le PostgreSQL alwaysdata,
le front sur Vercel. `COMPTE` désigne le nom de ton compte alwaysdata.

## 1. Base de données

Dans **Bases de données > PostgreSQL**, crée une base et un utilisateur.
L'hôte est `postgresql-COMPTE.alwaysdata.net`.

## 2. Code et configuration (en SSH)

Active l'accès SSH dans **Accès distant > SSH**, puis :

```bash
ssh COMPTE@ssh-COMPTE.alwaysdata.net
```

```bash
git clone https://github.com/jaimai/cadence.git ~/cadence
```

Le dépôt est privé : GitHub demandera un jeton d'accès personnel en lecture, ou
ajoute une clé de déploiement SSH au dépôt.

```bash
cp ~/cadence/apps/api/deploy/env.alwaysdata.example ~/cadence/apps/api/.env
```

Remplis `~/cadence/apps/api/.env` (les commentaires du fichier expliquent chaque
ligne), puis lance l'installation :

```bash
~/cadence/apps/api/deploy/alwaysdata.sh
```

Le script crée l'environnement Python, installe les dépendances et crée les tables.
L'API demande Python 3.11 ou plus récent : choisis la version dans
**Environnement > Python** avant de lancer le script.

## 3. Le site (l'API)

Dans **Web > Sites**, ajoute un site de type **Programme utilisateur** :

- **Adresses** : `COMPTE.alwaysdata.net` (ou ton domaine)
- **Commande** :
  ```
  /home/COMPTE/cadence/apps/api/.venv/bin/uvicorn app.main:app --host $IP --port $PORT --proxy-headers --forwarded-allow-ips=*
  ```
- **Répertoire de travail** : `/home/COMPTE/cadence/apps/api`

Vérification : `https://COMPTE.alwaysdata.net/api/health` doit répondre `{"ok":true}`.

## 4. Le worker

Dans **Avancé > Services**, ajoute un service :

- **Commande** : `/home/COMPTE/cadence/apps/api/.venv/bin/python -m app.worker`
- **Répertoire de travail** : `/home/COMPTE/cadence/apps/api`

Sans lui, rien n'est publié et les jetons TikTok et X expirent au bout de deux heures.

## 5. Relier le front Vercel

Le front appelle l'API sur son propre domaine, et Vercel relaie vers alwaysdata :
le cookie de session reste ainsi sur le domaine du front, sans réglage particulier.
Ajoute ces deux règles **au début** de `rewrites` dans `apps/web/vercel.json` :

```json
{ "source": "/api/:path*", "destination": "https://COMPTE.alwaysdata.net/api/:path*" },
{ "source": "/media-files/:path*", "destination": "https://COMPTE.alwaysdata.net/media-files/:path*" }
```

Ne définis pas `VITE_API_URL` dans Vercel avec cette méthode.

Deux adresses restent celles d'alwaysdata, directement :

- les URI de redirection à déclarer chez chaque réseau :
  `https://COMPTE.alwaysdata.net/api/oauth/<réseau>/callback` ;
- le serveur MCP : `https://COMPTE.alwaysdata.net/mcp/`.

## Mettre à jour

```bash
~/cadence/apps/api/deploy/alwaysdata.sh
```

Puis redémarre le site (**Web > Sites**) et le service worker (**Avancé > Services**).

## Si ça ne marche pas

- Les journaux du site et du service sont dans `~/admin/logs/`.
- Une erreur de connexion à la base au démarrage vient presque toujours de
  `DATABASE_URL` : le préfixe doit être `postgresql+asyncpg://`.
