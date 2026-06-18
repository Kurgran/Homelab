# V1.1 — Image LiteLLM augmentée de detect-secrets.
# On part de l'image officielle (le même binaire que la V1.0) et on
# ajoute UNE dépendance : detect-secrets. Le garde-fou (dlp_guardrail.py)
# l'importera en interne ; il doit donc être présent dans le même Python.
FROM ghcr.io/berriai/litellm:main-latest

# --no-cache-dir : pas de cache pip conservé dans l'image (image plus légère,
#   surface réduite). Version épinglée = build reproductible (réflexe supply-chain) :
#   on sait exactement ce qui tourne, pas de dérive silencieuse au prochain build.
#   NB : 1.5.0 noté de mémoire — à confirmer comme dernière stable sur PyPI.
RUN pip install --no-cache-dir detect-secrets==1.5.0
