"""
V1.1 — Garde-fou DLP : DÉTECTION seule de secrets dans les prompts.

Périmètre verrouillé (cf. Notion, Reprise 18/06/2026) :
  - on DÉTECTE un secret dans le prompt et on le LOGGE,
  - on ne masque PAS (c'est la V1.2), on ne bloque PAS.

Modèle mental : ce fichier N'EST PAS un service réseau. C'est une fonction
que LiteLLM appelle lui-même, à l'intérieur de son propre process Python,
AVANT de router le prompt vers Ollama (hook `pre_call`). Un seul conteneur,
un seul Python = LiteLLM + ce garde-fou + detect-secrets.

Invariant sécurité du projet : jamais de secret en clair dans les logs.
On ne logge que le TYPE du secret (ex. "AWS Access Key") et le compte,
jamais sa valeur (`secret.secret_value`).
"""

from typing import Literal, Optional, Union

# Briques LiteLLM : la classe de base à hériter, les types attendus par le hook,
# et le logger interne du proxy (apparaît dans les logs du conteneur).
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm.proxy._types import UserAPIKeyAuth
from litellm.caching.caching import DualCache
from litellm._logging import verbose_proxy_logger

# Briques detect-secrets :
#  - scan.scan_line(line) : scanne UNE ligne, yield des PotentialSecret.
#  - default_settings()   : charge les plugins par défaut (regex formats connus
#    + analyse d'entropie). SANS ce contexte, get_plugins() est vide → 0 détection.
from detect_secrets.core import scan
from detect_secrets.settings import default_settings


class DetectSecretsGuardrail(CustomGuardrail):
    def __init__(self, **kwargs):
        # On ne configure rien de spécial : on passe les kwargs au parent
        # (guardrail_name, mode, default_on… injectés depuis la config).
        super().__init__(**kwargs)

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
            for message in messages:
                content = message.get("content")
                # Un message peut être multimodal (liste) ; en V1.1 on ne traite
                # que le texte simple. Le reste est ignoré (pas une erreur).
                if not isinstance(content, str):
                    continue
                # scan_line travaille ligne par ligne : un prompt multi-lignes
                # doit être éclaté, sinon l'entropie d'une ligne est diluée.
                for line in content.splitlines():
                    for secret in scan.scan_line(line):
                        findings.append(secret.type)  # .type = libellé lisible

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
