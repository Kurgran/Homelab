# IA Zone de confiance

Mini-SMSI (système de management de la sécurité de l'information) appliqué à l'IA, monté dans mon homelab. L'objectif : démontrer la chaîne **exigence → contrôle → preuve** sur la sécurisation des flux vers les LLM — fuite de secrets, gouvernance, observabilité.

Le fil rouge : un même prompt contenant un secret, envoyé vers un LLM local (Ollama) puis vers un LLM cloud, montre que le masquage doit se produire **avant** le franchissement de la frontière de confiance — et que cette frontière ne se situe pas au même endroit selon le déploiement (le réseau local en interne, la passerelle Internet en cloud).

C'est la couche gouvernance et sécurité posée au-dessus de ma stack IA locale (voir [`../IA-Local`](../IA-Local)).

## Trois étages

- **Gouvernance** : politique d'usage IA, registre IA, analyse de risques.
- **Contrôle** : coffre de secrets + proxy IA avec garde DLP.
- **Assurance** : logs structurés, Wazuh, dashboard d'observabilité.

## Versions

V1 proxy DLP + Ollama · V2 backend cloud (comparaison des frontières) · V3 coffre de secrets (OpenBao) · V4 registre IA + politique · V5 dashboard d'observabilité · V6 Wazuh + analyse de risques EBIOS. Une version à la fois, chacune livrable seule.

## État

**V1.0 — proxy nu validé** : le proxy LiteLLM route les requêtes vers Ollama (sans filtre). Prochaine étape : la détection de secrets en V1.1. Détails et lancement dans [`proxy/`](proxy/).
