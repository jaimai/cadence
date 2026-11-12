# Cadence

Planification et publication de contenu sur les réseaux sociaux, pilotable depuis
l'interface web ou depuis un LLM via MCP. « Cadence » est un nom de travail.

## État

| Brique | État |
|---|---|
| Comptes, espaces de travail (multi-tenant), sessions | fait |
| Médiathèque (Cloudflare R2, ou disque local en dev) | fait |
| Posts : brouillon, planification, publication, relance des échecs | fait |
| Worker de publication (file d'attente dans Postgres) | fait |
| Connecteurs **Facebook Pages**, **Instagram**, **TikTok**, **LinkedIn**, **X** | faits, testés contre des API simulées, pas encore contre les vraies plateformes |
| Serveur MCP (clé API) | fait |
| Landing publique | fait |
| Pages entreprise LinkedIn | à faire (accès soumis à validation par LinkedIn) |
| OAuth pour le connecteur MCP (ajout direct dans claude.ai) | à faire |

## Structure

```
apps/api   FastAPI, SQLAlchemy, Alembic, worker, serveur MCP   (Python, uv)
apps/web   React, Vite, Tailwind                                (pnpm)
```

Points d'entrée utiles dans `apps/api/app` :

- `connectors/base.py` : le contrat d'un connecteur. Ajouter un réseau = une classe
  qui l'implémente, enregistrée dans `connectors/__init__.py`.
- `services/posts.py` : cycle de vie d'un post. L'API REST et les outils MCP passent
  tous les deux par là.
- `services/publisher.py` : le moteur exécuté par le worker.
- `mcp_server.py` : les outils exposés au LLM.

## Démarrer en local

Prérequis : Python 3.13 avec [uv](https://docs.astral.sh/uv/), Node 22 avec pnpm, PostgreSQL.

```bash
createdb cadence
cp apps/api/.env.example apps/api/.env   # renseigner DATABASE_URL et SECRET_KEY
pnpm install
pnpm migrate
```

Puis trois processus :

```bash
pnpm dev:api      # http://localhost:8000
pnpm dev:worker   # publie les posts arrivés à échéance
pnpm dev:web      # http://localhost:5173
```

Tests de l'API (base `cadence_test`, modifiable avec `TEST_DATABASE_URL`) :

```bash
pnpm test:api
```

En stockage `local`, les médias sont servis par l'API elle-même : les plateformes ne
peuvent pas les télécharger. Pour publier réellement un média, passer en `STORAGE_BACKEND=r2`.

## Connecter les réseaux

Pour chaque réseau, l'URI de redirection à déclarer est
`{API_BASE_URL}/api/oauth/<réseau>/callback` (`facebook`, `instagram`, `tiktok`,
`linkedin`, `x`).
Tant que les identifiants d'un réseau manquent, son bouton « Connecter » est remplacé
par un avertissement dans la page Comptes.

### Connexion par QR code

Le bouton « Connecter » affiche un QR code. Le scanner ouvre la connexion du réseau
sur le téléphone, là où changer de compte est le plus simple ; le compte apparaît
ensuite tout seul dans la page Comptes. Le code est valable 15 minutes et peut être
scanné plusieurs fois pour ajouter plusieurs comptes. « Continuer sur cet appareil »
garde la connexion classique dans le navigateur.

Le téléphone ouvre `API_BASE_URL` : le QR code ne fonctionne donc que si l'API est
accessible publiquement, pas sur `localhost`.

### Facebook

1. Créer une app sur developers.facebook.com, y ajouter « Facebook Login ».
2. Renseigner `META_APP_ID` et `META_APP_SECRET`.

En mode développement, l'app fonctionne pour les personnes ayant un rôle dessus et
les Pages qu'elles administrent, sans App Review. Permissions demandées :
`pages_show_list`, `pages_manage_posts`, `pages_read_engagement`.

### Instagram

Connexion par « Instagram Login » : pas besoin de Page Facebook liée, mais le compte
doit être professionnel ou créateur.

1. Dans la même app Meta, ajouter le produit Instagram et choisir
   « API setup with Instagram login ».
2. Renseigner `INSTAGRAM_APP_ID` et `INSTAGRAM_APP_SECRET` (différents de ceux de l'app Meta).

Permissions demandées : `instagram_business_basic`, `instagram_business_content_publish`.
Limites imposées par Instagram : un média obligatoire, images en JPG uniquement,
10 médias par carrousel ici. Une vidéo seule part en Reel. Le jeton dure 60 jours et
le worker le renouvelle tout seul.

### TikTok

1. Créer une app sur developers.tiktok.com avec les produits Login Kit et
   Content Posting API (option « Direct Post »), scopes `user.info.basic` et `video.publish`.
2. Renseigner `TIKTOK_CLIENT_KEY` et `TIKTOK_CLIENT_SECRET`.
3. **Vérifier le domaine des médias** (le domaine public du bucket R2) dans le portail
   TikTok : TikTok télécharge les fichiers depuis cette adresse et refuse les domaines
   non vérifiés (`url_ownership_unverified`).

Tant que l'app n'a pas passé l'audit TikTok :

- le compte TikTok lui-même doit être en **mode privé** ;
- les posts ne sont visibles que par leur auteur (`TIKTOK_PRIVACY_LEVEL=SELF_ONLY`).

Après l'audit, passer `TIKTOK_PRIVACY_LEVEL=PUBLIC_TO_EVERYONE`. L'audit demande que
l'utilisateur choisisse lui-même la visibilité et les interactions de chaque post :
ce sélecteur reste à ajouter dans le composer avant de déposer la demande.

Plusieurs comptes : connecter chaque compte l'un après l'autre, en changeant de compte
sur tiktok.com entre deux connexions. Le jeton d'accès dure 2 heures ; le worker le
renouvelle en continu, il doit donc tourner en permanence.

Formats : une vidéo, ou jusqu'à 35 photos JPG ou WebP.

### LinkedIn

Publication sur le **profil personnel** uniquement.

1. Créer une app sur developer.linkedin.com et y ajouter les produits
   « Sign In with LinkedIn using OpenID Connect » et « Share on LinkedIn »
   (scopes `openid`, `profile`, `w_member_social`).
2. Renseigner `LINKEDIN_CLIENT_ID` et `LINKEDIN_CLIENT_SECRET`.

Formats : texte seul, 1 à 20 images JPG ou PNG, ou une vidéo MP4 (500 Mo maximum
côté LinkedIn). Texte limité à 3 000 caractères.

Le jeton dure 60 jours. LinkedIn ne fournit un refresh token qu'à certaines apps :
sans lui, le compte passe en « à reconnecter » à l'expiration. Les pages entreprise
demandent la permission `w_organization_social`, accordée via la Community Management
API après validation par LinkedIn ; elles ne sont pas gérées ici.

`LINKEDIN_VERSION` fixe la version de l'API. LinkedIn retire chaque version au bout
d'un an environ : à mettre à jour de temps en temps.

### X

1. Créer une app sur developer.x.com, activer l'authentification OAuth 2.0 en type
   « Web App » avec les droits de lecture et d'écriture.
2. Renseigner `X_CLIENT_ID` et `X_CLIENT_SECRET`.

Scopes demandés : `tweet.read`, `tweet.write`, `users.read`, `media.write`,
`offline.access`. Formats : texte seul, jusqu'à 4 images (JPG, PNG, WebP) ou une vidéo.
Le texte est limité à `X_MAX_CHARS` caractères (280 par défaut) ; le décompte est un
simple nombre de caractères, alors que X compte les liens et certains emojis autrement.

L'accès en écriture à l'API X dépend de l'offre souscrite auprès de X : vérifier les
quotas et le tarif en vigueur avant de s'appuyer dessus.

LinkedIn et X reçoivent les fichiers envoyés par le serveur (et non une URL à
télécharger) : ils fonctionnent donc aussi avec le stockage `local`.

## Utiliser depuis un LLM (MCP)

Créer une clé dans Réglages, puis déclarer le serveur `{API_BASE_URL}/mcp/` avec
l'en-tête `Authorization: Bearer cad_...`. Avec Claude Code :

```bash
claude mcp add --transport http cadence https://api.mondomaine.com/mcp/ --header "Authorization: Bearer cad_..."
```

Par défaut, un post planifié par le LLM reste un brouillon « À valider » jusqu'à ce
qu'un humain l'approuve. Le réglage « Publication directe » lève cette étape.

## Déploiement

- **Base** : PostgreSQL alwaysdata. `DATABASE_URL` en `postgresql+asyncpg://`.
- **API et worker** : n'importe quel hébergeur Python. Deux processus :
  `uvicorn app.main:app` et `python -m app.worker`, précédés de `alembic upgrade head`.
  Un seul worker suffit ; en lancer plusieurs est sans danger (`SKIP LOCKED`).
- **Médias** : bucket Cloudflare R2 exposé sur un domaine public, avec une règle CORS
  autorisant `PUT` depuis l'origine du front (le navigateur envoie les fichiers
  directement à R2).
- **Front** : Cloudflare Pages, commande `pnpm build:web`, dossier `apps/web/dist`,
  variable `VITE_API_URL`.

Le front et l'API doivent partager le même domaine racine (`app.mondomaine.com` et
`api.mondomaine.com`) : la session est un cookie `SameSite=Lax`, qui ne passe pas
entre deux domaines sans rapport. En production, mettre `COOKIE_SECURE=true`.
