# Pensieve on a personal device: variations

> Companion to [SETUP.md](SETUP.md). The standard setup already covers a
> personal PC: sign in to Microsoft To Do and GitHub Copilot in the app's
> **Connect your accounts** screen and you are done. This page covers two
> variations.

---

## Using GitHub Models instead of Copilot

If the Copilot CLI is not an option, Pensieve can call GitHub Models with a
personal access token.

1. Create a fine-grained token at
   https://github.com/settings/personal-access-tokens/new with
   **Account permissions > Models: Read-only**.
2. Pick a model from https://github.com/marketplace/models
   (`openai/gpt-4o-mini` is a sensible default).
3. In `.env`:

   ```ini
   LLM_PROVIDER=github_models
   GITHUB_TOKEN=<your token>
   GITHUB_MODELS_MODEL=openai/gpt-4o-mini
   ```

4. Restart Pensieve. `pensieve init` should print `provider = github_models`.

Notes:

- The **AI models** panel applies to the Copilot provider only; with GitHub
  Models the model comes from `GITHUB_MODELS_MODEL`.
- GitHub Models has free-tier rate limits. If a big first sync hits a 429,
  wait a few minutes and sync again: only tasks that are still unenriched are
  sent.
- Task titles and notes go to GitHub Models for enrichment; see
  https://docs.github.com/en/github-models for its data handling.
- Some corporate networks block `models.github.ai`; use Copilot there.

Azure OpenAI is the third option (`LLM_PROVIDER=azure_openai`, plus
`AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT`; keyless through
`DefaultAzureCredential`, or `AZURE_OPENAI_API_KEY`).

---

## Keeping work and personal tasks apart

One Pensieve data directory holds one board. The simplest way to keep a work
board and a personal board apart on the same PC is a second clone of the repo
with its own `.env`, set to another port so both can run at once:

```ini
PENSIEVE_BACKEND_PORT=8766
```

Each clone keeps its own `data/`: Accounts choices (`connections.json`), model
choices (`ai-models.json`), Microsoft sign-in, ChromaDB store, and goals.
To get a desktop app for the second clone, build it with
`.\desktop\build.ps1 -NoShortcuts` so it does not replace the first clone's
`Pensieve` shortcuts, and pin `desktop\dist\Pensieve.exe` yourself.

Within a single board, `PENSIEVE_RECAP_LIST_NAMES` already keeps personal
lists out of Connect recaps.

---

## Troubleshooting

**"This copy of Pensieve has no Microsoft app id yet"** → set
`PERSONAL_GRAPH_CLIENT_ID` (see [desktop/SHARING.md](desktop/SHARING.md)).

**Microsoft sign-in is rejected** → the app registration must allow personal
Microsoft accounts and have **Allow public client flows** turned on.

**"Microsoft did not allow adding tasks"** → reconnect Microsoft in
**More > Accounts** so Pensieve can ask for `Tasks.ReadWrite` (older sign-ins
only granted read access).

**To revoke Pensieve's Microsoft access** → **More > Accounts > Disconnect**,
or delete `data/ms-token-cache.bin`.
