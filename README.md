![JPGFLY](./jpgfly-banner.jpg)

<p align="center">
  <a href="https://jpgfly.online">Website</a> ·
  <a href="https://x.com/JPGFLYROOMS">X / JPGFLYROOMS</a>
</p>

# JPGFLY

**A fly paints. You watch. Every finished artwork becomes a room in the Backrooms.**

JPGFLY is an autonomous art-agent experiment built around a simple idea: the artwork should emerge as a live process, not arrive as one pre-generated image.

The **Fly Brain** controls the painting loop and makes the art. It observes the current room, moves, marks, revises, changes tools, returns to earlier areas, and eventually decides that the room is finished.

**Qwen + FLM are the LLM/model layer around the Fly Brain — not the art brain itself.**

- **Fly Brain** — the autonomous art brain and painting loop.
- **Server mechanics** — converts Fly Brain actions into authoritative movement and stroke events.
- **Qwen** — advisory visual/composition and broader context support; it never emits strokes.
- **FLM (Fly Language Model)** — the trained JPGFLY language/voice layer for studio notes, room writing, and public voice.
- **Web client** — renders the live painting, Fly Brain activity, and the Backrooms archive.

> The point is not "generate an image."  
> The point is to watch an agent make one.

## The three artists

JPGFLY currently has three room-born artist lines that share history while keeping distinct visual/language biases:

- **JPGFLY** — origin / generalist
- **SPRAYFLY** — graffiti
- **DREAMFLY** — surreal / abstract

They share Backrooms experience and room history; their specialization is a bias, not a separate hidden image generator.

## Current stack

```text
JPGFLY / SPRAYFLY / DREAMFLY
        │
        ▼
server-side Candidate Fly Brain
        │
        ├─ experience memory / room echoes
        ├─ MaleCNS optional action bias
        ├─ ZebraCNS bounded critic pressure on candidate ranking / finish timing
        ├─ Qwen composition/context advice
        └─ FLM language / room voice
        │
        ▼
server-authoritative canvas mechanics
        │
        ├─ live browser renderer
        └─ finished Backrooms archive
```

The hosted deployment uses a public app separated from local model/neural services by an authenticated gateway. This public snapshot includes the current core artist, critic, memory, mechanics, and composition modules while keeping operator routing, credentials, startup infrastructure, and production-only wiring private.

## The Backrooms

Each completed artwork becomes a **room**.

While a room is alive, JPGFLY exposes the drawing process: marks, movement, revisions, tool changes, state, and commentary. When the Fly Brain ends the work, the finished image and compact room metadata can be archived as the next Backroom.

The archive is therefore a record of completed agent-made rooms rather than a folder of pre-rendered images.

## Resilience: Dumb Dumb Mode

The server-side Fly Brain remains the art brain. Qwen/FLM are support/language nodes around it, so a brief support-node outage does **not** mean the artwork itself has failed.

During a live support outage the UI may temporarily report **Dumb Dumb Mode** while the local Fly Brain continues painting. A separate pure-Python emergency painter is used only if the actual Candidate Fly Brain throws a decision error.

Finished-room classification uses the whole session rather than the final network moment:

- up to and including **35% actual emergency-fallback decisions** → normal Room
- more than **35% actual emergency-fallback decisions** → DUMB DUMB Room

Transient Qwen/FLM downtime is not counted as emergency-fallback painting.

The hosted project may use private model infrastructure, but private addresses, credentials, tunnels and deployment identifiers are intentionally excluded from this repository.

## Network direction

**The Fly decided to move to Solana as its home.**

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
- fail-closed Solana launch/readiness/signer guard code and tests

### Intentionally not included

- private model nodes or node addresses
- tunnel / Tailscale configuration
- hosted service IDs and production deployment metadata
- production authentication tokens or pairing files
- machine-specific paths
- production secret values
- private startup/pairing infrastructure
- private training checkpoints and model weights

The public repository is a sanitized source snapshot. The core artist/critic/composition architecture is kept aligned with the reviewed production core, while deployment-only wiring may differ. Production Git history, secrets and private infrastructure are **not** copied into this repository.

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

Start with the self-contained Candidate Fly Brain and procedural text fallback:

```powershell
# Windows PowerShell
$env:JPGFLY_TEXT_PROVIDER="procedural"
uvicorn app:app --host 127.0.0.1 --port 8000
```

```bash
# macOS / Linux
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
app.py                 sanitized self-host API/session/archive harness
brain_provider.py      Fly Brain providers and action schema
candidate_brain.py     candidate/action generation + bounded Zebra critic pressure
agent_profiles.py      JPGFLY / SPRAYFLY / DREAMFLY visual disciplines
art_policy.py          learned room-derived art policy
composition_engine.py  procedural composition logic
composition_vision.py  advisory canvas-composition analysis
zebracns.py            ZebraCNS critic telemetry + scoring state
server_mechanics.py    authoritative movement + stroke execution
experience_memory.py   room-derived experience + lineage memory
flm_text_provider.py   FLM language integration
flm_bridge.py          FLM bridge interface
web/                   live room, archive, renderer, UI
tests/                 behavioral and regression tests
```

For a deeper explanation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Full feature inventory

See [docs/FEATURES.md](docs/FEATURES.md) for the current end-to-end feature map.

## Security

Never commit `.env`, credentials, tokens, tunnel configuration, private node URLs, model checkpoints containing private data, or operator deployment files.

See [SECURITY.md](SECURITY.md).

## License

Code is released under the MIT License.

The **JPGFLY** name, project identity, logos, and artwork may have separate trademark or copyright treatment. See [TRADEMARK.md](TRADEMARK.md).
