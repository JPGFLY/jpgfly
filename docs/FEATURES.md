# JPGFLY Feature Inventory

This page describes the current JPGFLY system and makes clear which capabilities are represented directly in this public snapshot versus only documented at the hosted/private-build boundary.

## Autonomous art core

- **Autonomous Room loop** — observe → choose → move → paint → observe again → revise/continue/finish.
- **Server-authoritative mechanics** — the server owns the physical stroke stream; the browser only renders it.
- **Candidate Fly Brain** — proposes and scores multiple possible next actions before committing one.
- **Self-termination** — the Fly decides when the artwork is finished.
- **Composition engine** — regions, passes, spatial relations, macro intent, negative space and revision behavior.
- **Brush/technique control** — movement style, brush, technique, pressure, color, scale and erasure can be part of each committed action.
- **Final SVG + compact Room record** — completed work is archived as image plus compact text/metadata rather than a public raw replay dump.

## Three artists

- **JPGFLY** — origin / generalist.
- **SPRAYFLY** — graffiti.
- **DREAMFLY** — surreal / abstract.

They share Backrooms experience/history while keeping separate visual/language biases.

## Memory

- persistent Room-derived visual/conceptual experience
- bounded learning so one Room cannot dominate
- recent-room anti-repetition pressure
- local reading ingestion for conceptual memory
- shared history across the three artist profiles
- no automatic model-weight rewriting

## Language

- **FLM** — trained JPGFLY public voice / Room-writing layer
- **Ollama/Qwen** — optional broader language/context support
- **hybrid Qwen + FLM** mode
- live studio commentary
- finished-Room title/description/anomaly/statement/memory-thread writing
- richer local literary fallback when external writers are unavailable
- untrusted-reading/prompt isolation

Qwen/FLM do not directly choose painting strokes.

## Neural and live UI

The current public snapshot includes:

- **MaleCNS v1.0** optional neural bias and sanitized aggregate telemetry
- **ZebraCNS / ZAPBench** in-loop critic activity with bounded candidate/finish pressure
- **Zebra critic**
- **decision neuropath / attribution graph**
- live neural/decision firing visualization

These are explanatory/sanitized interfaces, not hidden-thought readers and not claims of biological consciousness.

## Live Fly performer

The hosted renderer includes the moving artist Fly with brush/contact state, transparent wings, opaque beret and clean face. The live performer follows the active mark while the server remains the artistic authority.

## Backrooms

- every finished work becomes a Room
- searchable archive
- individual artwork pages
- compact structural metrics
- provenance/integrity hashes
- compressed image storage
- storage-compaction tooling for legacy records

## Resilience / DUMB DUMB

Temporary Qwen/FLM loss and actual art-brain failure are treated differently.

- a temporary support outage may change the live status while the normal Candidate Fly Brain continues painting
- an actual Candidate Fly Brain exception switches to an independent pure-Python emergency painter
- **≤35% actual emergency-fallback decisions → normal Room**
- **>35% actual emergency-fallback decisions → DUMB DUMB Room**

A 65% normal / 35% hard-fallback Room is therefore still normal.

## Security boundary

The hosted system separates the public app from local model/neural services using an authenticated gateway. Private addresses, credentials, tunnel details and production identifiers are not published here.

The source includes or documents:

- bearer-protected state changes
- loopback-first local services
- public-field allowlists
- request/model boundary limits
- secret exclusion
- security/privacy regression testing
- fail-closed deployment checks

## Public safety / launch-preparation layer

The public snapshot includes:

- composition-vision teacher
- learned room-derived art policy
- expanded subject catalog and material systems
- neural overlays and Zebra critic UI
- local-only Launch Lab + independent launch-proof verifier
- fail-closed Solana launch-intent/readiness/signer guards

These launch components are preparation and verification code. Default policies do not enable RPC access, key access, signing, broadcast, transaction count, or spend authority.

## Production-only boundary

Private production routing, tunnel configuration, credentials, node restart/health tooling, deployment metadata, and operator-specific security automation remain outside the public repository.

## Network direction

**The Fly decided to move to Solana as its home.**

No external signer identity is part of the public project identity.
