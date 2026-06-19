"""
V1.3 — Garde-fou DLP : MASQUAGE de secrets + JOURNALISATION JSON structurée.

Périmètre verrouillé (cf. Notion) :
  - on DÉTECTE un secret dans le prompt (réutilise les deux passes de V1.1),
  - on le MASQUE : la valeur ressort caviardée ([SECRET_MASQUE]) côté LLM,
  - on LOGGE uniquement le TYPE et le compte (jamais la valeur),
  - un prompt légitime passe INTACT (aucune valeur détectée → aucun remplacement).

Modèle mental : ce fichier N'EST PAS un service réseau. C'est une fonction
que LiteLLM appelle lui-même, à l'intérieur de son propre process Python,
AVANT de router le prompt vers Ollama (hook `pre_call`). Un seul conteneur,
un seul Python = LiteLLM + ce garde-fou + detect-secrets.

Invariant sécurité du projet (NON négociable) : le masquage PRÉCÈDE la
journalisation. La valeur du secret ne quitte jamais ce hook — on ne logge
que le TYPE du secret (ex. "AWS Access Key") et le compte, jamais sa valeur.

--------------------------------------------------------------------------
ARCHITECTURE DE LA DÉTECTION (inchangée depuis V1.1, option (c))

Deux passes indépendantes sur la même ligne, puis fusion :

  PASSE A — formats connus (regex). On boucle sur les détecteurs de
    detect-secrets EN EXCLUANT les 2 plugins d'entropie. Chirurgical : ne
    matche que ce qui a la STRUCTURE d'un secret connu (clé AWS, token
    GitHub/Stripe…). L'objet PotentialSecret expose la valeur matchée via
    `.secret_value` (vérifié au source detect-secrets 1.5.0) → c'est cette
    valeur qu'on masquera.

  PASSE B — formats inconnus (gate maison longueur + entropie). On tokenise
    nous-mêmes la ligne ; un token n'est retenu que s'il passe DEUX seuils :
    longueur >= MIN_TOKEN_LEN ET entropie de Shannon > ENTROPY_THRESHOLD.
    Ici le TOKEN lui-même EST la valeur à masquer.

--------------------------------------------------------------------------
NOUVEAUTÉ V1.2 — du « renvoyer les types » au « masquer + logger »

  `_scan_line` ne renvoie plus une seule liste de types. Il renvoie DEUX
  listes séparées par conception :
    - `values` : les chaînes à MASQUER (servent au remplacement, ne sortent
       JAMAIS du code, ne sont JAMAIS loggées) ;
    - `types`  : les libellés à TRACER (seuls à entrer dans le log).
  Cette séparation rend l'invariant difficile à violer : l'instruction de log
  ne référence physiquement que `types`. Pour fuiter une valeur il faudrait
  aller délibérément chercher l'autre liste.

  Le MASQUAGE se fait dans le hook (le chef d'orchestre), pas dans `_scan_line`
  (l'ouvrier qui ne voit qu'une ligne). Raison : le hook tient le `content`
  complet du message ; un `str.replace` sur le contenu entier ignore les
  retours à la ligne → pas de recollage fragile des lignes.

  On remplace par VALEUR (Route 2), pas par offset/position. La détection nous
  donne la valeur, pas les colonnes ; et un remplacement par valeur est
  insensible aux décalages de position (réflexe data : tokenisation par
  substitution > redaction positionnelle qui casse dès qu'un index bouge).
"""

import json
import re
from datetime import datetime, timezone
from typing import Literal, Optional, Union

# Briques LiteLLM : la classe de base à hériter, les types attendus par le hook,
# et le logger interne du proxy (apparaît dans les logs du conteneur).
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm.proxy._types import UserAPIKeyAuth
from litellm.caching.caching import DualCache
from litellm._logging import verbose_proxy_logger

# Briques detect-secrets :
#  - default_settings() : contexte qui charge les plugins par défaut. SANS lui,
#    get_plugins() renvoie une liste vide → 0 détection.
#  - get_plugins()      : renvoie les instances de détecteurs configurés (27 par
#    défaut en 1.5.0). On va filtrer cette liste pour ne garder que les formats.
#  - HighEntropyStringsPlugin : classe mère des 2 plugins d'entropie
#    (Base64/Hex). Sert à les RECONNAÎTRE pour les EXCLURE de la passe A.
#  - Base64HighEntropyString : on s'en sert UNIQUEMENT pour réutiliser sa
#    méthode calculate_shannon_entropy() dans notre passe B.
from detect_secrets.settings import default_settings, get_plugins
from detect_secrets.plugins.high_entropy_strings import (
    HighEntropyStringsPlugin,
    Base64HighEntropyString,
)

# --- Boutons de réglage (arbitrages FP / FN) -------------------------------
# Longueur minimale d'un token candidat. 20 = ordre de grandeur des clés/tokens
# réels ; en dessous on est presque sûr d'avoir un mot de langage naturel.
MIN_TOKEN_LEN = 20
# Seuil d'entropie de Shannon (base64). 4.5 = défaut de Base64HighEntropyString
# dans detect-secrets. Au-dessus = "ça ressemble à de l'aléatoire".
ENTROPY_THRESHOLD = 4.5
# Jeton de remplacement. Court, basse entropie, aucun format connu → il ne sera
# JAMAIS re-flaggé par nos propres passes (pas de boucle de re-détection).
MASK_TOKEN = "[SECRET_MASQUE]"
# Découpe une ligne en tokens "candidats secrets" : on coupe sur tout ce qui
# n'appartient PAS à l'alphabet base64/url-safe. Les espaces, ponctuation, etc.
# deviennent des séparateurs → "Ma cle est AKIA..." donne ["Ma","cle","est","AKIA..."].
_TOKEN_SPLIT = re.compile(r"[^A-Za-z0-9+/\-_=]+")
# Libellé de nos détections d'entropie maison (le .type qu'on logge).
_ENTROPY_LABEL = "High Entropy String (custom gate)"

# Une seule instance, réutilisée pour le CALCUL d'entropie (pas pour scanner).
_ENTROPY_CALC = Base64HighEntropyString(limit=ENTROPY_THRESHOLD)


class DetectSecretsGuardrail(CustomGuardrail):
    def __init__(self, **kwargs):
        # On ne configure rien de spécial : on passe les kwargs au parent
        # (guardrail_name, mode, default_on… injectés depuis la config).
        super().__init__(**kwargs)

    def _scan_line(self, line: str, format_plugins) -> tuple:
        """
        Scanne UNE ligne et renvoie DEUX listes parallèles :
          - values : les chaînes exactes à masquer (servent au remplacement) ;
          - types  : les libellés correspondants (seuls à être loggés).
        Les deux listes sont alignées par index (values[i] ↔ types[i]) mais on
        ne les manipule jamais ensemble dans le log — c'est tout l'intérêt.
        `format_plugins` = liste pré-filtrée des détecteurs non-entropie.
        """
        values = []
        types = []

        # PASSE A — formats connus (regex). analyze_line renvoie un set de
        # PotentialSecret ; on prend .secret_value (à masquer) ET .type (à logger).
        for plugin in format_plugins:
            for secret in plugin.analyze_line(
                filename="adhoc-prompt-scan",  # nom factice : pas de fichier réel
                line=line,
                line_number=0,
            ):
                if secret.secret_value:  # garde-fou : jamais de remplacement de ""
                    values.append(secret.secret_value)
                    types.append(secret.type)

        # PASSE B — formats inconnus (gate maison longueur + entropie).
        # Ici le token lui-même est la valeur à masquer.
        for token in _TOKEN_SPLIT.split(line):
            if len(token) < MIN_TOKEN_LEN:
                continue  # trop court → mot de langage naturel, on jette
            if _ENTROPY_CALC.calculate_shannon_entropy(token) > ENTROPY_THRESHOLD:
                values.append(token)
                types.append(_ENTROPY_LABEL)

        return values, types

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,   # qui a appelé (identité) — non utilisé ici
        cache: DualCache,                    # cache partagé LiteLLM — non utilisé ici
        data: dict,                          # LA requête : data["messages"] = le prompt
        call_type: Literal[
            "completion",
            "text_completion",
            "embeddings",
            "image_generation",
            "moderation",
            "audio_transcription",
            "pass_through_endpoint",
            "rerank",
        ],
    ) -> Optional[Union[Exception, str, dict]]:
        """
        Appelé par LiteLLM AVANT le routage. On scanne chaque message, on
        REMPLACE chaque valeur détectée par [SECRET_MASQUE] dans le contenu,
        puis (et seulement après) on logge les TYPES. On renvoie `data` MUTÉ :
        c'est la version caviardée qui franchit la frontière de confiance.
        """
        messages = data.get("messages", [])
        all_types = []  # ne contient QUE des types de secrets, jamais de valeur

        # Le contexte charge/décharge proprement les plugins autour du scan.
        with default_settings():
            # On filtre UNE fois la liste des détecteurs : on retire les 2
            # plugins d'entropie (on gère l'entropie nous-mêmes en passe B).
            format_plugins = [
                p for p in get_plugins()
                if not isinstance(p, HighEntropyStringsPlugin)
            ]

            for message in messages:
                content = message.get("content")
                # Un message peut être multimodal (liste) ; on ne traite que le
                # texte simple. Le reste est ignoré (pas une erreur).
                if not isinstance(content, str):
                    continue

                # 1) DÉTECTION : on collecte valeurs + types sur tout le message.
                msg_values = []  # valeurs de CE message — locales, jamais loggées
                for line in content.splitlines():
                    values, types = self._scan_line(line, format_plugins)
                    msg_values.extend(values)
                    all_types.extend(types)

                # 2) MASQUAGE (avant tout log) : on remplace chaque valeur dans
                #    le contenu complet. On déduplique et on traite les plus
                #    longues d'abord — si une valeur est sous-chaîne d'une autre,
                #    on évite de corrompre le remplacement de la plus longue.
                if msg_values:
                    masked = content
                    for value in sorted(set(msg_values), key=len, reverse=True):
                        masked = masked.replace(value, MASK_TOKEN)
                    # Réécriture in place → data["messages"] est muté pour LiteLLM.
                    message["content"] = masked

        # 3) JOURNALISATION : APRÈS le masquage, et sur les TYPES uniquement.
        #    V1.3 — on n'émet plus un message texte mais un ÉVÉNEMENT JSON
        #    structuré. Le dict ne contient QUE des champs non sensibles :
        #    la valeur du secret n'a littéralement aucune clé où atterrir
        #    (garantie structurelle, prolongement des deux listes de V1.2).
        if all_types:
            event = {
                # Marqueur FIXE : c'est sur cette valeur que le decoder Wazuh
                # (V6) reconnaîtra une détection DLP, sans matcher du texte fragile.
                "event": "dlp_secret_detected",
                # Horodatage ISO 8601 en UTC, posé par nous : pas d'ambiguïté de
                # fuseau quand le log voyagera vers Wazuh (autre VLAN/serveur).
                "ts": datetime.now(timezone.utc).isoformat(),
                # Combien de hits sur ce prompt (≠ nombre de secrets distincts,
                # nuance de métrique notée pour le dashboard V5).
                "secret_count": len(all_types),
                # Libellés des types détectés UNIQUEMENT (jamais les valeurs).
                "secret_types": all_types,
                # Modèle ciblé tel que reçu dans la requête (alias de la config,
                # ex. "local-llama"). .get() = pas de KeyError si absent.
                "model": data.get("model"),
            }
            # json.dumps SÉRIALISE le dict en chaîne JSON valide (échappement des
            # caractères spéciaux géré par la lib → toujours parsable).
            # ensure_ascii=False : on garde les accents lisibles (é, è) au lieu
            # de séquences \uXXXX. WARNING = niveau "événement à remonter".
            verbose_proxy_logger.warning(json.dumps(event, ensure_ascii=False))
        else:
            # Prompt légitime : AUCUN événement de détection émis (critère V1.3 :
            # "pas de faux événement"). On reste en DEBUG texte simple, qui ne
            # pollue pas le flux que Wazuh écoutera (il ne ciblera que le JSON).
            verbose_proxy_logger.debug(
                "DLP detect-secrets : aucun secret détecté dans le prompt"
            )

        # On renvoie la requête MUTÉE : le prompt caviardé part vers le backend.
        return data
