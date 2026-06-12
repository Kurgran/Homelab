# Proxy DLP — V1.0 (proxy nu)

Un proxy **LiteLLM** route les requêtes vers **Ollama** (LLM local), sans masquage pour l'instant. Objectif de la brique : prouver que le flux traverse le proxy avant d'y greffer la détection de secrets (V1.1).

## Architecture réseau

Le proxy rejoint le réseau Docker **existant** d'Ollama (`ai-sovereign-stack_default`), déclaré `external` dans le compose. Il joint Ollama par **nom de service** (`http://ollama:11434`, plan interne), jamais via `localhost` ni le port publié sur l'hôte.

```
curl :4000  ──►  LiteLLM (proxy)  ──►  ollama:11434  ──►  réponse
```

## Lancer

Prérequis : la stack IA-Local (Ollama) doit tourner — c'est elle qui crée le réseau `ai-sovereign-stack_default`.

```bash
# 1. Vérifier le modèle Ollama installé
docker exec ollama ollama list

# 2. Adapter la ligne `model:` de litellm-config.yaml si besoin (ollama/<tag exact>)

# 3. Démarrer
docker compose up -d
docker compose logs -f litellm     # Ctrl+C pour quitter

# 4. Tester le routage via le proxy (port 4000, pas 11434)
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"local-llama","messages":[{"role":"user","content":"dis bonjour en un mot"}]}'
```

Une réponse JSON avec le texte du modèle dans `choices[0].message.content` valide la brique.

## Dettes de sécurité connues (à traiter en durcissement)

- Proxy publié en `0.0.0.0:4000` **sans authentification** → joignable par tout le VLAN. À fermer par une clé maître LiteLLM.
- Ollama publié en `0.0.0.0:11434` : ce port hôte n'est requis par aucun service interne (ils le joignent par nom). Candidat au retrait pour fermer l'exposition.
- Médiation à imposer : pour que le proxy soit un vrai contrôle, repointer OpenWebUI vers lui et couper les chemins directs vers Ollama (un contrôle contournable n'en est pas un).
