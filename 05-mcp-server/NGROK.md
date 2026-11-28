# Exposition MCP via ngrok (plateforme Agentic)

Les serveurs MCP locaux sont exposés en HTTPS pour que la plateforme Agentic
puisse les voir et appeler leurs outils comme des services cloud.

> Les URL ci-dessous sont celles de la session ngrok en cours. Elles changent
> au redémarrage de l'agent : relever les valeurs via
> `http://127.0.0.1:4040/api/tunnels` puis mettre à jour la configuration de
> la plateforme.

| Serveur | Port local | URL publique |
|---|---:|---|
| base-donnees | 8201 | `https://b1d8-105-188-16-23.ngrok-free.app/mcp` |
| base-connaissances | 8203 | `https://e6bf-105-188-16-23.ngrok-free.app/mcp` |
| canaux | 8204 | `https://b537-105-188-16-23.ngrok-free.app/mcp` |

## En-têtes requis

Chaque appel MCP doit contenir :

- `X-API-Key` : valeur lue dans le `.env` local du serveur (**jamais** dans un
  fichier versionné ni dans le workflow exporté) ;
- `ngrok-skip-browser-warning: true` (évite la page d'avertissement ngrok).

La configuration MCP enregistrée dans la plateforme Agentic est prioritaire
sur celle exportée avec le workflow : c'est là que les deux en-têtes doivent
être renseignés. Format attendu par le composant `MCP Tools` :

```json
{
  "name": "base-connaissances",
  "config": {
    "url": "https://e6bf-105-188-16-23.ngrok-free.app/mcp",
    "headers": {
      "X-API-Key": "<valeur lue dans le .env local>",
      "ngrok-skip-browser-warning": "true"
    },
    "verify_ssl": true
  }
}
```

Les trois valeurs `X-API-Key` et les URL sont regroupées hors dépôt dans
`C:\Users\PC\AppData\Local\Temp\opencode\mcp_connexion.json`.

> Le workflow exporté `workflowJugeVf.json` contient encore `headers: {}` :
> sans configuration MCP côté plateforme, les runs Agentic échouent avec
> `Failed to connect via Streamable HTTP` / `Timeout updating tool list`.

## Outils vérifiés

- `base-donnees` : `lire`, `ecrire`
- `base-connaissances` : `chercher`
- `canaux` : `envoyer_whatsapp`, `envoyer_email`, `verifier_templates`

## Workflow JUGE

`C:\Users\PC\Downloads\workflowJugeVf.json` a été mis à jour pour utiliser
l'URL ngrok de `base-connaissances`.

Les clients Agentic injectent aussi un tweak Langflow pour que les champs
`limite` et `offset` du composant `MCP Tools` soient des entiers :

```json
{"MCP Tools": {"limite": 100, "offset": 0}}
```

Sans ce tweak, le run JUGE échoue avec `Input should be a valid integer`.

## Redémarrage

```powershell
ngrok start soukna-mcp-base soukna-mcp-connaissances soukna-mcp-canaux
```

Le compte ngrok gratuit est limité à 3 endpoints par session d'agent ; le
quatrième tunnel (`soukna-mcp-portail`, port 8202) est défini dans la config
mais n'est pas démarré dans la même session.
