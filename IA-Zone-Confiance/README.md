# IA Zone de confiance

J'ai monté ce projet dans mon homelab pour répondre à une question simple : quand un secret (une clé API, un token) se retrouve par erreur dans un prompt, à quel moment et à quel endroit faut-il l'arrêter ?

L'idée est de traiter mon propre labo comme une petite boîte qui devrait sécuriser ses usages d'IA. Écrire les règles, poser les garde-fous techniques, et garder des traces qui prouvent que ça tient.

La démo qui résume tout : j'envoie le même prompt contenant un faux secret vers un modèle local (Ollama), puis vers un modèle cloud. On voit alors que le masquage doit se faire avant que la donnée ne quitte ma zone de confiance, et que cette zone ne s'arrête pas au même endroit selon qu'on reste en local ou qu'on part dans le cloud.

C'est la couche gouvernance et sécurité que je pose au-dessus de ma stack IA locale (voir [`../IA-Local`](../IA-Local)).

## Comment c'est découpé

Trois niveaux, chacun pour une question différente. Le quoi et le pourquoi : une politique d'usage et un registre des systèmes d'IA. Le comment technique : un coffre à secrets et un proxy qui inspecte les flux. Et la preuve : des logs propres, Wazuh pour les alertes, un tableau de bord pour lire l'état d'un coup d'œil.

## Les versions

Je construis par paliers, un seul à la fois, chacun utilisable seul :

- V1 : un proxy qui filtre devant Ollama
- V2 : on ajoute un backend cloud et on compare les deux frontières
- V3 : un vrai coffre à secrets (OpenBao)
- V4 : le registre des usages et la politique
- V5 : le tableau de bord d'observabilité
- V6 : Wazuh branché dessus et une analyse de risques EBIOS

## Où j'en suis

V1.0 est faite : le proxy LiteLLM relaie bien les requêtes vers Ollama. Pour l'instant il ne filtre rien, c'était l'étape « est-ce que le tuyau passe ». La détection de secrets arrive en V1.1. Le détail et le lancement sont dans [`proxy/`](proxy/).
