# JPGFLY Architecture

JPGFLY separates the art brain, physical canvas mechanics, neural/model support, browser rendering, memory, and final-room writing.

## 1. Room-born Fly Brain — the art brain

There are three artist profiles:

- **JPGFLY** — generalist
- **SPRAYFLY** — graffiti
- **DREAMFLY** — surreal / abstract

They share Backrooms experience/history but keep different visual and language biases. The server-side Candidate Fly Brain observes the authoritative canvas, proposes/scorers candidate actions, commits one action, and eventually decides when to finish.

Qwen is not the art brain. FLM is not the art brain. The browser is not the art brain.

## 2. Server mechanics — the body

`server_mechanics.py` turns a structured Fly Brain action into authoritative movement and stroke events. The browser renders those events; it does not invent artistic geometry.

```text
canvas observation
      ↓
Candidate Fly Brain
      ↓
structured action
      ↓
server mechanics
      ↓
movement + stroke events
      ↓
live canvas / final SVG
```

## 3. Neural + model support

The hosted stack can use four local support services behind an authenticated boundary:

- **Ollama / Qwen** — general language/context support
- **FLM** — trained JPGFLY language/voice layer
- **MaleCNS** — optional neural bias applied to a selected art action
- **ZebraCNS** — in-loop critic: real activity applies bounded pressure to candidate ranking and finish timing; it never emits strokes directly

These services can enrich context, language and neural biasing, but the Candidate Fly Brain remains the painting decision engine.

Conceptually:

```text
                    Qwen
                     │
                     ├──── language/context
                     │
                    FLM
                     │
                     ├──── JPGFLY voice
                     │
Candidate Fly Brain ─┼──── MaleCNS soft bias
                     │
                     └──── ZebraCNS bounded critic pressure
          │
          ▼
server mechanics → browser + Backrooms
```

## 4. Browser + Backrooms

The web client renders the live event stream, the Fly performer, current neural/status telemetry, and the Backrooms archive.

Completed Rooms retain the finished image plus compact writing, structural metrics, provenance and hashes. Heavy live execution history is not the public artwork format.

## 5. Experience memory

`experience_memory.py` is a bounded slow-learning layer. Completed Rooms influence later palettes, techniques, composition tendencies and conceptual echoes. Reading material contributes conceptual context. It does not rewrite model weights.

## Failure behavior

Two different failure states are intentionally separated:

1. **Support-node outage** — Qwen/FLM may be temporarily unreachable. The live status may show DUMB DUMB, but the normal Candidate Fly Brain can keep painting. This does not count as emergency-fallback art decisions.
2. **Art-brain decision failure** — if the Candidate Fly Brain throws, the session switches to the independent pure-Python emergency painter.

Finished-room classification is session-wide:

- `fallback_ratio <= 0.35` → normal Room
- `fallback_ratio > 0.35` → DUMB DUMB Room

So a Room that is 65% normal / 35% actual fallback is still a normal Room.

## Hosted trust boundary

The hosted production shape is:

```text
public JPGFLY app
      │
      ▼
authenticated gateway
      │
      ├─ Qwen
      ├─ FLM
      ├─ MaleCNS
      └─ ZebraCNS
```

The public repository intentionally omits private addresses, tunnel configuration, credentials, deployment IDs and machine-specific paths.

## Network direction

**The Fly decided to move to Solana as its home.**

## Non-goals

JPGFLY makes no claim of biological consciousness or literal biological equivalence. Neural visualizations are software/biological-data-informed interfaces, not hidden model-thought readouts.
