# JPGFLY 6.4 release notes

## Painting architecture

JPGFLY 6.4 separates painting from language generation.

```text
canvas observation
      |
      v
Fly Brain (Python)
      |
      +-- proposes 8 candidate actions
      +-- scores them against canvas state
      +-- uses visual/conceptual memory
      |
      v
selected action
      |
      +-- optional MaleCNS v1.0 bias
      |
      v
server-authoritative movement + stroke
```

Qwen and FLM are language layers. They can produce live studio notes and finished-room writing, but they do not choose painting strokes.

## MaleCNS boundary

The optional MaleCNS integration uses MaleCNS v1.0 connectome topology with simulated neural dynamics and an engineered canvas-to-neural interface. This is a software simulation and art interface, not a claim of biological consciousness.

The MaleCNS dataset, trained models, private endpoints, and production tunnel configuration are not bundled with this repository.

## Resilience

Painting does not require Qwen or FLM. If those language services become unavailable, the Fly Brain keeps painting.

Each session also owns an independent procedural emergency painter. If the richer Candidate Fly Brain raises an unexpected decision error, that room switches permanently to:

```text
DUMB DUMB MODE · PURE PYTHON FALLBACK
```

This keeps the room alive while clearly marking it as degraded.

## Live renderer

The live page now treats the server event stream as authoritative. Existing strokes are reconstructed from received server events, preventing browser animation/backlog state from leaving a valid painting visually blank.

## Security boundary

Recommended local-only model endpoints:

- Ollama/Qwen: 127.0.0.1:11434
- FLM: 127.0.0.1:4680
- MaleCNS: 127.0.0.1:4690

Do not expose raw model services directly to the public internet. Use a narrow authenticated gateway if remote access is required.

Production credentials, tunnel configuration, hosted service IDs, local datasets, checkpoints, and machine-specific startup files remain outside this public repository.
