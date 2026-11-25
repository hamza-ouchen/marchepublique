# JUGE — export Agentic AI à partager

Le fichier [workflowJugeVf.json](workflowJugeVf.json) est l'export natif fourni par
Ouchen Hamza le 25 novembre 2026. Il est conservé à l'identique, sans modification
des nœuds, des connexions, des prompts ou des expressions JQ.

**Périmètre de cet export : revue documentaire avec extraction IA contrainte.**
Sa description indique « Publication bloquee ». Il ne constitue pas une version
autonome du JUGE capable de sélectionner un lot, d'appliquer les quatre contrôles
d'éligibilité et d'enregistrer des verdicts.

## Importer

1. Télécharger le fichier JSON depuis GitHub avec le bouton de téléchargement du
   fichier brut ; ne pas enregistrer la page HTML de GitHub sous une extension JSON.
2. Dans Agentic AI d'Abafusion, importer le JSON comme nouveau workflow.
3. Vérifier les composants et les ports après import : l'export indique la version
   `1.7.0` et contient 16 nœuds et 18 connexions. La compatibilité avec d'autres
   versions ou avec Langflow n'a pas été testée.
4. Rattacher les connexions MCP et les credentials à votre propre environnement.
5. Vérifier le contrat de données ci-dessous avant de lancer le workflow.

## Configuration après import

| Élément | Configuration nécessaire |
| --- | --- |
| `MCPTools-I6bpL` | Sélectionner un serveur et l'outil correspondant au rapport attendu |
| Connexion MCP | URL de votre service et secret dans le gestionnaire de credentials |
| OpenRouter | Credential personnel ; modèle configuré : `openai/gpt-4o-mini` |
| Sources documentaires | Passages réellement disponibles et traçables, au format attendu |

Le champ `tool` du nœud MCP est **vide** dans le fichier fourni. Ses en-têtes MCP
et sa clé OpenRouter ne contiennent aucune valeur d'authentification dans cet export.
Ils doivent être configurés dans l'interface après import.

L'URL ngrok personnelle présente dans l'export est une configuration de poste,
pas un hébergement partagé garanti. La remplacer ou rattacher le nœud à votre
propre connexion MCP. Ne jamais ajouter les clés, mots de passe, URI PostgreSQL
authentifiées ou exports non expurgés au dépôt.

## Contrat de données observé dans les expressions JQ

Le premier normalisateur (`DataOperations-OZD8W`) attend une enveloppe contenant
un tableau `results` avec exactement un élément. Le champ `results[0].text` doit
être une chaîne JSON représentant un rapport avec :

```json
{
  "status": "blocked",
  "publication_authorized": false,
  "persisted": false,
  "calculated_verdict": null,
  "reason": "RULES_NOT_APPROVED",
  "ai_input": []
}
```

Cet exemple décrit le format, pas un résultat de recette exécuté. Une réponse au
format différent produit `MCP_REPORT_INVALID`.

Le chemin vers OpenRouter est activé lorsque `reason` vaut `RULES_NOT_APPROVED`
et que `ai_input` contient exactement **8 passages**. Sinon, l'interprétation est
marquée `not_run` avec `INSUFFICIENT_APPROVED_SOURCES`.

Le prompt demande uniquement des citations exactes dans un tableau `constats`.
Le garde-fou vérifie notamment les clés, la présence de chaque citation dans le
passage correspondant et les identifiants de preuve/contrôle ; la publication
du verdict reste bloquée.

**Attention au raccordement au MCP du projet :** son outil standard `chercher`
retourne un objet avec `passages`, `vide`, `hitl`, etc. Cet objet ne correspond pas
directement au rapport ci-dessus. Un adaptateur explicite est nécessaire ;
sélectionner simplement `chercher` ne suffit pas à rendre ce workflow opérationnel.
L'export ne contient pas de nœud MCP de lecture des tables ni d'écriture `verdicts`.

## Vérifications de publication

- JSON parsé avec Python, 16 identifiants de nœuds uniques et 18 connexions vers
  des nœuds existants.
- Graphe sans cycle ni nœud isolé.
- Copie identique au fichier source, empreinte SHA-256 :
  `ac10a8ca4df399ae7ced9e670b8004c1bbe26a4b85af68ee816b738e0201be73`.
- Recherche des secrets connus de la configuration locale et de formats courants
  de tokens/URI authentifiées : aucune correspondance détectée. Les champs de
  credentials inspectés sont vides ; cette recherche n'est pas exhaustive.
- Aucun import ni lancement de cet export dans Agentic AI n'a été effectué pendant
  cette opération de publication. Aucun test de verdict, d'écriture ou de retour
  A2A n'est revendiqué.

Vérification JSON reproductible depuis la racine du dépôt :

```powershell
python -m json.tool 03-agentic-ai/juge/workflowJugeVf.json > $null
```

Pour le JUGE complet, consulter aussi `03-agentic-ai/agent-cards/juge.agent-card.json`
et la section JUGE du README racine. L'acceptation fonctionnelle et la revue par
un autre membre restent nécessaires avant intégration et utilisation opérationnelle.
