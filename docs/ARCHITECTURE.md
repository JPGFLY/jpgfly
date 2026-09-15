# JPGFLY Architecture

JPGFLY is easiest to understand as four separate layers.

## 1. Fly Brain — the art brain

The **Fly Brain** is the autonomous painting system.

It owns the room-level art process: observing the current canvas state, choosing how to continue, moving, making marks, revising, changing tools/techniques, building composition, and eventually ending the artwork.

The public project language intentionally calls this the **art brain**.

Qwen is not the Fly Brain. FLM is not the Fly Brain.

## 2. Server mechanics — the body

The Fly Brain does not paint pixels directly.

It emits structured actions. Server mechanics turn those actions into authoritative physical events such as movement, strokes, pressure/tool behavior, timing, and canvas updates.

This gives JPGFLY a separation between:

```text
intention / art process
        ↓
     Fly Brain
        ↓
structured action
        ↓
 server mechanics
        ↓
movement + stroke events
        ↓
      canvas
```

That separation is important because the artwork can be replayed/rendered from the event stream rather than treated as a single opaque generated bitmap.

## 3. Qwen + FLM — the LLM/model layer

**Qwen + FLM sit around the Fly Brain as model/language services.**

### Qwen

Qwen is the general LLM/model component used by the hosted experiment where model assistance is enabled.

It is not presented publicly as "the art engine." The art identity belongs to the Fly Brain.

### FLM — Fly Language Model

FLM is the trained JPGFLY language layer.

It handles areas such as:

- public voice
- studio notes
- finished-room writing
- language/personality continuity
- contextual text generation

FLM does not directly paint the image.

Self-hosters may run procedural-only mode, Qwen, FLM, hybrid configurations, or their own compatible services.

## 4. Web / Backrooms layer

The web client renders the live event stream and exposes the current room.

A completed artwork can become a **Backroom** containing the finished image and compact metadata/text derived from the session.

Conceptually:

```text
                 ┌──────────────┐
                 │  Qwen + FLM  │
                 │ model / text │
                 └──────┬───────┘
                        │
                        │ context / language support
                        ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│ canvas state │ → │  FLY BRAIN   │ → │ server mechanics │
└──────────────┘   │   ART BRAIN  │   └────────┬─────────┘
                   └──────────────┘            │
                                               ▼
                                      movement / strokes
                                               │
                                               ▼
                                          live canvas
                                               │
                                               ▼
                                       finished Backroom
```

## Failure behavior

External model availability should not determine whether the room can continue existing.

JPGFLY includes a procedural fallback known publicly as **Dumb Dumb Mode**. If an optional model service disappears, the Fly Brain can continue producing actions instead of simply stopping the artwork.

## Public agent identity

The public JPGFLY identity currently exposes two addresses:

- **Agent wallet:** `EvkMVctzE6VP82KvPzSwrtpLkcygwyhvUHnVZZAtTDZG`
- **JPGFLY token:** `0xE34d22a71D59569740B8e9781CfD0469Cd26030C`

These are public identifiers only. Wallet private keys, signing authority, custody, and deployment secrets are not part of this repository.

## Production boundary

This public repository does **not** describe or expose the operator's real production topology.

Excluded from the open-source snapshot are:

- production model-node addresses
- private tunnels and routing
- production service IDs
- authentication and pairing material
- machine-specific paths
- private model weights/checkpoints
- operator secrets

Self-hosters provide their own infrastructure and endpoints through environment configuration.
