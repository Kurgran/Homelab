# Projet 2 — Identity & Zero Trust sur Azure

Exploration du domaine Identity & Access sur Azure : Entra ID, RBAC, PIM, Conditional Access, journaux d'audit.

Compte Azure PAYG · Tenant : compte personnel · Durée : 2 sessions

---

## Ce qui a été fait

| Fonctionnalité | Statut | Remarque |
|---|---|---|
| Exploration Entra ID (tenant, users, groupes, rôles) | ✅ Fait | — |
| RBAC pratique — assignation rôle Lecteur sur resource group | ✅ Fait | Scope : Projet-Azure-1 |
| Identités managées — vérification dans IAM | ✅ Fait | VM Projet 1 → rôle Contributeur |
| Journaux de connexion Entra ID | ✅ Fait | 7j rétention sur compte free |
| Journaux d'audit Entra ID | ✅ Fait | Événement Add user retrouvé |
| PIM — configuration pratique | ⚠️ Non testé | Licence Entra ID P2 requise |
| Conditional Access — politique custom | ⚠️ Non testé | Licence Entra ID P1/P2 requise |

---

## Concepts clés

**Rôles Entra ID ≠ Azure RBAC** : deux systèmes indépendants. Être Global Administrator dans Entra ID ne donne aucun droit sur les ressources Azure, et inversement.

**Protocoles d'authentification** : Entra ID utilise OIDC (authentification) et OAuth2 (autorisation). Kerberos reste limité aux environnements hybrides on-premise.

**RBAC — notion de scope** : un rôle s'hérite vers le bas. Assigné à l'abonnement, il couvre tous les resource groups. Assigné à un resource group, il ne couvre que ce périmètre.

**PIM — Just-In-Time** : rôle "eligible" plutôt que permanent. L'utilisateur demande l'élévation pour une durée limitée avec justification. Nécessite Entra ID P1 ou P2.

**Conditional Access** : politiques SI/ALORS sur les accès. Si appareil non reconnu ET hors réseau de confiance → MFA ou blocage. Nécessite Entra ID P1 ou P2.

**Journaux de connexion vs journaux d'audit** : les journaux de connexion tracent les authentifications (qui s'est connecté, depuis où). Les journaux d'audit tracent les actions d'administration (création d'un utilisateur, modification d'un rôle, changement d'une politique).

---

## Limitation licence

Le trial Entra ID P2 est refusé sur les comptes Azure PAYG personnels. Le Microsoft 365 Developer Program (qui aurait fourni un tenant E5 avec P2 inclus) refuse également les comptes personnels depuis 2023. PIM et Conditional Access ont été étudiés en théorie et les interfaces explorées — sans configuration pratique possible dans ce contexte.

---

## Points d'examen AZ-500 / SC-500

- Global Administrator dans Entra ID ≠ droits sur les ressources Azure
- OIDC pour l'authentification, pas Kerberos
- PIM et Conditional Access nécessitent au minimum Entra ID P1
- Différence entre rôle *eligible* (JIT) et rôle *active* (permanent)
- Password Spraying : 1 mot de passe × N comptes — détectable dans les journaux de connexion

---

## Projet suivant

[Projet 3 — Defender for Cloud + Microsoft Sentinel](../Projet-3-Defender-Sentinel/)
