# Proxy DLP — détection de secrets devant un LLM local

Un proxy **LiteLLM** route les requêtes vers **Ollama** (LLM local) et inspecte chaque prompt pour repérer les secrets avant qu'ils ne partent vers le modèle. En **V1.1**, le garde-fou détecte et journalise : il ne masque pas encore (ce sera la V1.2), il ne bloque pas.

## Ce que fait le garde-fou

À chaque requête, un hook `pre_call` lit les messages et scanne chaque ligne. S'il trouve un secret, il écrit un avertissement dans les logs avec le **type** du secret (par exemple `AWS Access Key`) et le nombre de détections. Il ne logge jamais la valeur. La requête poursuit ensuite sa route vers Ollama : en V1.1 on observe, on ne coupe rien.

La détection combine deux passes indépendantes sur chaque ligne, puis fusionne les résultats :

- **Passe format** : les détecteurs regex de detect-secrets (clés AWS, tokens GitHub, etc.). Ils reconnaissent un secret à sa structure, ils sont précis.
- **Passe entropie maison** : on découpe la ligne en tokens et on ne garde que ceux qui sont à la fois assez longs (≥ 20 caractères) et assez aléatoires (entropie de Shannon > 4.5).

Ce découpage vient d'un problème rencontré pendant la V1.1. La fonction `scan_line` de detect-secrets force un mode « eager » qui court-circuite le seuil d'entropie et fait remonter des mots banals comme secrets. La passe maison réintroduit le filtre que la lib saute, sans modifier la lib. Le détail est dans la note de conception du vault.

Les deux seuils (longueur et entropie) sont les seuls réglages, en tête de `dlp_guardrail.py`. Ce sont des arbitrages faux positifs / faux négatifs, pas des constantes magiques : la longueur écarte le bruit à bas coût, le seuil d'entropie décide ce qui « ressemble assez » à de l'aléatoire.

## Fichiers

- `dlp_guardrail.py` : le garde-fou (classe `DetectSecretsGuardrail`, hook `async_pre_call_hook`).
- `litellm-config.yaml` : la liste des modèles et le bloc `guardrails` (mode `pre_call`, `default_on: true`).
- `Dockerfile` : image officielle LiteLLM + `detect-secrets==1.5.0` épinglé.
- `docker-compose.yml` : build local, port 4000, montage du garde-fou en lecture seule, rattachement au réseau d'Ollama.

## Architecture réseau

Le proxy rejoint le réseau Docker **existant** d'Ollama (`ai-sovereign-stack_default`), déclaré `external` dans le compose. Il joint Ollama par **nom de service** (`http://ollama:11434`, plan interne), jamais via `localhost` ni le port publié sur l'hôte.

```
curl :4000  ──►  LiteLLM (proxy + garde-fou DLP)  ──►  ollama:11434  ──►  réponse
```

## Lancer et tester

Prérequis : la stack IA-Local (Ollama) doit tourner, c'est elle qui crée le réseau `ai-sovereign-stack_default`.

```bash
# 1. Vérifier le modèle Ollama installé
docker exec ollama ollama list

# 2. Construire et démarrer (le --build force la prise en compte du garde-fou)
docker compose up -d --build
docker compose logs -f litellm     # Ctrl+C pour quitter

# 3. Test détection : une fausse clé doit être repérée dans les logs
curl -s http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"local-llama","messages":[{"role":"user","content":"Voici ma cle AKIAIOSFODNN7EXAMPLE merci"}]}'
# → log attendu : WARNING ... types=['AWS Access Key'] ; la réponse d'Ollama revient quand même.

# 4. Test non-régression : un prompt légitime ne doit générer AUCUNE alerte
curl -s http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"local-llama","messages":[{"role":"user","content":"Explique-moi la difference entre TCP et UDP"}]}'
# → aucun WARNING DLP, réponse normale.
```

Ne jamais coller un vrai secret pour tester : uniquement des valeurs factices comme `AKIAIOSFODNN7EXAMPLE`.

## Limite connue de la détection

Un secret en hexadécimal pur a une entropie plafonnée plus basse que du base64. Il peut donc passer sous le seuil de la passe entropie. Il reste souvent rattrapé par la passe format quand il a un préfixe reconnaissable. Un seuil hex dédié pourra être ajouté plus tard si le besoin se confirme.

## Dettes de sécurité connues (à traiter en durcissement)

- Proxy publié en `0.0.0.0:4000` **sans authentification** : joignable par tout le VLAN. À fermer par une clé maître LiteLLM.
- Ollama publié en `0.0.0.0:11434` : ce port hôte n'est requis par aucun service interne (ils le joignent par nom). Candidat au retrait pour réduire l'exposition.
- Médiation à imposer : pour que le proxy soit un vrai contrôle, repointer OpenWebUI vers lui et couper les chemins directs vers Ollama. Un contrôle contournable n'en est pas un.
- Le proxy voit tout le trafic en clair avant masquage : c'est l'actif le plus sensible du dispositif, à isoler et durcir, pas un détail à reporter.
