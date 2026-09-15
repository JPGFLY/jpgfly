# JPGFLY

**A fly paints. You watch. Every finished artwork becomes a room in the Backrooms.**

JPGFLY is an autonomous art-agent experiment built around a simple idea: the artwork should emerge as a live process, not arrive as one pre-generated image.

The **Fly Brain** controls the painting loop and makes the art. It observes the current room, moves, marks, revises, changes tools, returns to earlier areas, and eventually decides that the room is finished.

**Qwen + FLM are the LLM/model layer around the Fly Brain — not the art brain itself.**

- **Fly Brain** — the autonomous art brain and painting loop.
- **Server mechanics** — converts Fly Brain actions into authoritative movement and stroke events.
- **Qwen** — general LLM/model support for context and language-layer reasoning.
- **FLM (Fly Language Model)** — the trained JPGFLY language/voice layer for studio notes, room writing, and public voice.
- **Web client** — renders the live painting, Fly Brain activity, and the Backrooms archive.

> The point is not "generate an image."  
> The point is to watch an agent make one.

## The Backrooms

Each completed artwork becomes a **room**.

While a room is alive, JPGFLY exposes the drawing process: marks, movement, revisions, tool changes, state, and commentary. When the Fly Brain ends the work, the finished image and compact room metadata can be archived as the next Backroom.

The archive is therefore a record of completed agent-made rooms rather than a folder of pre-rendered images.

## Resilience: Dumb Dumb Mode

The Fly Brain is designed to keep painting even when an external model layer is unavailable.

If Qwen/FLM disappears, JPGFLY can fall back to a procedural instinct mode — **Dumb Dumb Mode** — instead of freezing the room.

The hosted project may use private model infrastructure, but that infrastructure is intentionally not part of this repository.

## Public agent identity

**Live:** https://jpgfly.online  
**X / Backrooms:** https://x.com/JPGFLYROOMS  
**GitHub:** https://github.com/JPGFLY/jpgfly

### Agent wallet

```
0x977d02F5519be02Cc3B8905e1D39f916DC4A3e9D
```

### JPGFLY token

```
0xE34d22a71D59569740B8e9781CfD0469Cd26030C
```

The wallet and token addresses are public project identifiers. Private keys, signing authority, custody, and deployment secrets remain outside the open-source repository.

## Open-source boundary

This repository is a **sanitized source snapshot** of the private operational project.

It includes the code needed to understand, run, inspect, fork, and experiment with JPGFLY, while deliberately excluding the operator's production infrastructure.

### Included

- Fly Brain and composition logic
- server mechanics
- web rendering code
- archive/session logic
- Qwen/FLM integration interfaces
- tests
- generic self-host configuration
- security and architecture documentation

### Intentionally not included

- private model nodes or node addresses
- tunnel / Tailscale configuration
- hosted service IDs and production deployment metadata
- production authentication tokens or pairing files
- machine-specific paths
- production secret values
- private startup/pairing infrastructure
- private training checkpoints and model weights
- the production fly raster artwork

Private source snapshot:

```
d43f1413b6f2f87cf4b144dc0ee5c362f5000835
```

The private repository's Git history was **not** copied into this public repository.

## Local quick start

Python 3.11+ recommended.

```bash
python -m venv .venv
```

Activate it:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start with the self-contained procedural Fly Brain:

```powershell
# Windows PowerShell
$env:JPGFLY_BRAIN_PROVIDER="procedural"
$env:JPGFLY_TEXT_PROVIDER="procedural"
uvicorn app:app --host 127.0.0.1 --port 8000
```

```bash
# macOS / Linux
export JPGFLY_BRAIN_PROVIDER=procedural
export JPGFLY_TEXT_PROVIDER=procedural
uvicorn app:app --host 127.0.0.1 --port 8000
```

Then open:

```
http://127.0.0.1:8000/live
```

To attach your own Qwen/FLM services, copy `.env.example` and supply **your own** local or self-hosted endpoints and credentials.

## Repository map

```text
app.py                 API, sessions, archive, public studio state
brain_provider.py      Fly Brain providers and action schema
candidate_brain.py     candidate/action generation
composition_engine.py  composition logic
server_mechanics.py    authoritative movement + stroke execution
experience_memory.py   room-derived experience memory
flm_text_provider.py   FLM language integration
flm_bridge.py          FLM bridge interface
web/                   live room, archive, renderer, UI
tests/                 behavioral and regression tests
```

For a deeper explanation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Security

Never commit `.env`, credentials, tokens, tunnel configuration, private node URLs, model checkpoints containing private data, or operator deployment files.

See [SECURITY.md](SECURITY.md).

## License

Code is released under the MIT License.

The **JPGFLY** name, project identity, logos, and artwork may have separate trademark or copyright treatment. See [TRADEMARK.md](TRADEMARK.md).
