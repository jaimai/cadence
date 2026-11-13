# Déployer le back sur Railway

Un seul service fait tout : au démarrage il met la base à jour, puis il sert l'API
et fait tourner le worker de publication dans le même processus. Il n'y a donc ni
commande de démarrage ni second service à configurer.

## 1. Créer le projet

1. Sur railway.com : **New Project > Deploy from GitHub repo**, choisis `jaimai/cadence`.
2. Dans le service créé : **Settings > Source > Root Directory** : `apps/api`.
   Railway y trouve le `Dockerfile` et construit l'image avec.

## 2. La base

Soit une base Railway (**Create > Database > PostgreSQL**), soit n'importe quelle
base PostgreSQL existante dont tu mets l'adresse dans `DATABASE_URL`.

## 3. Variables du service

Dans **Variables**, ajoute :

| Variable | Valeur |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}`, ou l'adresse de ta base (`postgresql://utilisateur:motdepasse@hote:5432/base`) |
| `SECRET_KEY` | une longue valeur aléatoire (commande ci-dessous) |
| `ENCRYPTION_KEY` | une clé de chiffrement (commande ci-dessous) |
| `WEB_BASE_URL` | l'adresse du front, par exemple `https://ton-projet.vercel.app` |
| `COOKIE_SECURE` | `true` |

Pour générer `SECRET_KEY` :

```bash
openssl rand -base64 48
```

Pour générer `ENCRYPTION_KEY` :

```bash
openssl rand -base64 32 | tr '+/' '-_'
```

`ENCRYPTION_KEY` chiffre les jetons des comptes connectés : une fois des comptes
connectés, ne la change plus. Les identifiants des réseaux (`META_APP_ID`,
`TIKTOK_CLIENT_KEY`...) s'ajoutent au même endroit ; la liste est dans
`apps/api/.env.example`.

Pas besoin de définir l'adresse de l'API ni le port : ils sont repris de Railway.

## 4. Rendre l'API accessible

**Settings > Networking > Generate Domain**. Note l'adresse obtenue
(`xxx.up.railway.app`), puis vérifie que `https://xxx.up.railway.app/api/health`
répond `{"ok":true}`.

Facultatif : **Settings > Deploy > Healthcheck Path** : `/api/health`, pour que Railway
n'envoie le trafic vers une nouvelle version qu'une fois qu'elle répond.

## 5. Relier le front Vercel

Ajoute ces deux règles **au début** de `rewrites` dans `apps/web/vercel.json`, avec
l'adresse de l'étape 4 :

```json
{ "source": "/api/:path*", "destination": "https://xxx.up.railway.app/api/:path*" },
{ "source": "/media-files/:path*", "destination": "https://xxx.up.railway.app/media-files/:path*" }
```

Le front appelle alors l'API sur son propre domaine et Vercel relaie : le cookie de
session reste sur le domaine du front. Ne définis pas `VITE_API_URL` dans Vercel.

Deux adresses restent celles de Railway, directement :

- les URI de redirection à déclarer chez chaque réseau :
  `https://xxx.up.railway.app/api/oauth/<réseau>/callback` ;
- le serveur MCP : `https://xxx.up.railway.app/mcp/`.

## 6. Après ton inscription

Crée ton compte sur le front, puis ajoute la variable `ALLOW_SIGNUP` = `false` pour
fermer les inscriptions.

## Médias

Sans autre réglage, les fichiers importés sont écrits dans le conteneur et **perdus
à chaque redéploiement**. Deux solutions :

- **Volume Railway** : ajoute un volume au service (par exemple monté sur `/data`).
  Les médias y sont rangés automatiquement. Suffisant pour LinkedIn et X.
- **Cloudflare R2** : voir [`R2.md`](R2.md). Obligatoire pour Instagram, TikTok et
  Facebook, qui téléchargent les médias par une URL publique.

## Mises à jour

Chaque push sur `main` redéploie le service. Les migrations de base s'appliquent
au démarrage.

## Ne pas multiplier les instances sans y penser

Le worker tourne dans le service de l'API. Passer à plusieurs réplicas reste sûr
(deux workers ne publient jamais le même post), mais si tu veux séparer les rôles :
mets `EMBED_WORKER=false` sur l'API et crée un second service, même dépôt et même
dossier, avec la commande de démarrage `python -m app.worker`.
