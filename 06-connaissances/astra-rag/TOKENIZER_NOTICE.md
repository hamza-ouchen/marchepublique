# Tokenizer E5 de référence

Le fichier de données `sou9na_rag/assets/e5_tokenizer.json` provient du modèle public
`intfloat/e5-large-unsupervised`, modèle parent indiqué par NVIDIA pour
`nvidia/nv-embedqa-e5-v5`.

Source : https://huggingface.co/intfloat/e5-large-unsupervised/blob/main/tokenizer.json

SHA-256 figé et contrôlé au chargement :
`5fd1c882abbd30517dced455a2c9768945ec726b96727927e4959348d9de550b`.

Le tokenizer est utilisé localement pour le découpage, sans poids du modèle et sans
transmettre les textes à Hugging Face. Les données sont conservées dans leur forme
originale. Le modèle E5 est publié sous licence MIT (voir sa fiche de modèle pour
les notices d'origine). BERT WordPiece est employé par ce tokenizer.

La limite opérationnelle NVIDIA est de 512 tokens. Le code impose 480 tokens locaux
pour laisser une marge au prétraitement du service. Le compteur du tokenizer parent
n'est pas prétendu strictement identique à celui du service : le premier refus réel
annonçait 561 tokens pour 559 tokens locaux. Chaque insertion reste validée par Astra.
Une erreur de fournisseur bloque la publication du manifeste ; aucun passage n'est
tronqué silencieusement et la collection existante n'est pas reconfigurée.

Référence NVIDIA :
https://docs.api.nvidia.com/nim/reference/nvidia-nv-embedqa-e5-v5
