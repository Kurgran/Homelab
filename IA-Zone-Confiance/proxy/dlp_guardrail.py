"""
V1.1 — Garde-fou DLP : DÉTECTION seule de secrets dans les prompts.

Périmètre verrouillé (cf. Notion) :
  - on DÉTECTE un secret dans le prompt et on le LOGGE,
  - on ne masque PAS (c'est la V1.2), on ne bloque PAS.

Modèle mental : ce fichier N'EST PAS un service réseau. C'est une fonction
que LiteLLM appelle lui-même, à l'intérieur de son propre process Python,
AVANT de router le prompt vers Ollama (hook `pre_call`). Un seul conteneur,
un seul Python = LiteLLM + ce garde-fou + detect-secrets.

Invariant sécurité du projet : jamais de secret en clair dans les logs.
On ne logge que le TYPE du secret (ex. "AWS Access Key") et le compte,
jamais sa valeur (`secret.secret_value`).

--------------------------------------------------------------------------
REFONTE DÉTECTION (option (c) — deux passes séparées et spécialisées)

Pourquoi on n'utilise PLUS `scan.scan_line` :
  scan_line force le mode *eager* de detect-secrets, qui court-circuite le
  filtre de seuil d'entropie → chaque mot banal ("TCP", "et", "la") ressort
  comme "High Entropy String". Faux positifs massifs (vérifié au source 1.5.0).

À la place, deux passes indépendantes sur la même ligne, puis fusion :

  PASSE A — formats connus (on délègue à la lib, ce qu'elle fait bien)
    On boucle sur les détecteurs de detect-secrets EN EXCLUANT les 2 plugins
    d'entropie. Les détecteurs de format (regex) sont chirurgicaux : ils ne
    matchent que ce qui a la STRUCTURE d'un secret connu (clé AWS, token
    GitHub/Stripe…). Eager/non-eager ne les concerne pas (c'est une
    spécificité des seuls plugins d'entropie).

  PASSE B — formats inconnus (notre gate maison, la lib ne sait pas le faire
    proprement en adhoc). On tokenise nous-mêmes la ligne, et on ne retient
    un token que s'il passe DEUX seuils :
      (1) longueur >= MIN_TOKEN_LEN  → écarte à bas coût les mots courts
          (un vrai secret est long ; "TCP" fait 3 caractères). Filtre de
          FAUX POSITIFS peu risqué : on rate rarement un vrai secret avec ça.
      (2) entropie de Shannon > ENTROPY_THRESHOLD → distingue une chaîne
          aléatoire d'un mot long mais structuré. C'est le bouton à double
          tranchant : trop BAS = faux positifs ; trop HAUT = on rate un vrai
          secret (faux négatif). On réutilise le calcul d'entropie EXPOSÉ par
          la lib (pas de réimplémentation maison de la formule).

  Division du travail : regex = formats connus / entropie = formats inconnus.
  « En parallèle » = séparation LOGIQUE (deux filtres dans la même fonction),
  pas de threads ni d'async.

Les deux constantes ci-dessous sont les seuls "boutons" de réglage. À
documenter comme des ARBITRAGES faux positifs / faux négatifs, pas comme des
valeurs magiques.
"""

import re
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

    def _scan_line(self, line: str, format_plugins) -> list:
        """
        Scanne UNE ligne et renvoie une liste de TYPES de secrets (jamais les
        valeurs). Combine la passe A (formats) et la passe B (entropie maison).
        `format_plugins` = liste pré-filtrée des détecteurs non-entropie.
        """
        found_types = []

        # PASSE A — formats connus (regex). analyze_line renvoie un set de
        # PotentialSecret ; on ne garde que .type, jamais .secret_value.
        for plugin in format_plugins:
            for secret in plugin.analyze_line(
                filename="adhoc-prompt-scan",  # nom factice : pas de fichier réel
                line=line,
                line_number=0,
            ):
                found_types.append(secret.type)

        # PASSE B — formats inconnus (gate maison longueur + entropie).
        for token in _TOKEN_SPLIT.split(line):
            if len(token) < MIN_TOKEN_LEN:
                continue  # trop court → mot de langage naturel, on jette
            if _ENTROPY_CALC.calculate_shannon_entropy(token) > ENTROPY_THRESHOLD:
                found_types.append(_ENTROPY_LABEL)

        return found_types

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,   # qui a appelé (identité) — non utilisé en V1.1
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
        Appelé par LiteLLM AVANT le routage. On lit les messages, on scanne
        chaque ligne, on logge les détections. On renvoie `data` INCHANGÉ
        (détection seule). Renvoyer data tel quel = laisser passer la requête.
        """
        messages = data.get("messages", [])
        findings = []  # on n'y stocke QUE des types de secrets, jamais les valeurs

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
                # Un message peut être multimodal (liste) ; en V1.1 on ne traite
                # que le texte simple. Le reste est ignoré (pas une erreur).
                if not isinstance(content, str):
                    continue
                # On scanne ligne par ligne : l'entropie d'une ligne entière
                # serait diluée, et nos tokens doivent rester isolés.
                for line in content.splitlines():
                    findings.extend(self._scan_line(line, format_plugins))

        if findings:
            # WARNING : visible même hors --detailed_debug. On logge le COMPTE
            # et les TYPES — surtout pas secret.secret_value.
            verbose_proxy_logger.warning(
                "DLP detect-secrets : %d secret(s) détecté(s) dans le prompt — types=%s",
                len(findings),
                findings,
            )
        else:
            verbose_proxy_logger.debug(
                "DLP detect-secrets : aucun secret détecté dans le prompt"
            )

        # V1.1 = détection seule : aucune altération, aucun blocage.
        return data
