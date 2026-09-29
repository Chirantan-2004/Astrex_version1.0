# ASTRAX — Prototype Specification

## 1. Source framing

Problem Statement: **SIH26174 — AI Human Activity Recognition for On-board BAS Experiment**.

The Team NEXUS deck names the proposed product **ASTRAX** and describes the flow:

**Camera Input → Understand → Validate Sequence → Guide Astronaut → Record Experiment → Monitor & Stream**.

## 2. Prototype objective

Demonstrate a complete, auditable experiment-supervision loop on a normal laptop:

1. Acquire a camera frame or deterministic demo observation.
2. Extract perception signals.
3. Infer an activity with a confidence score.
4. Require temporal consistency before committing the activity.
5. Compare the activity with the current protocol state.
6. If valid, advance and announce the next step.
7. If invalid, retain the protocol state, raise an alert, explain expected vs detected, and provide corrective guidance.
8. Persist a timestamped event.
9. Record local experiment video when a camera is available.
10. Expose a loopback MJPEG stream; do not advertise LAN access until relay authentication is implemented.
11. Present all telemetry in a mission-control GUI.

## 3. Demonstration protocol

```text
1 OPEN
2 PICK
3 INSERT
4 ROTATE
5 CLOSE
```

This is a **prototype demonstration protocol**, not a claim that these are the complete official BAS experiment steps.

## 4. System architecture

```text
Camera / Video File
      ↓
OpenCV Video Service
      ↓
Vision Engine
  ├─ YOLO pose (optional)
  ├─ OpenCV color/motion fallback
  └─ hand/object interaction
      ↓
Activity Observation
      ↓
Temporal Confidence Filter
      ↓
Deterministic Protocol Engine
      ├─ VALID → next step + guidance
      └─ OUT_OF_ORDER → voice alert + corrective guidance
      ↓
SQLite Event Memory + MP4
      ↓
Mission GUI + JSON/CSV + LAN Stream
```

## 5. Acceptance criteria

### Core
- Dashboard loads locally.
- Experiment starts and resets cleanly.
- Temporal filter requires three consistent observations.
- Automatic supervision only consumes distinct, fresh observations within a one-second window; stale sensing fails closed.
- Protected mission controls require OIDC or the explicit loopback-only local demo bypass.
- Crew messages persist locally as queued until an authenticated ground relay exists.
- Correct activity advances the protocol.
- Wrong activity does not advance the protocol.
- Wrong activity produces an expected-vs-detected explanation.
- Voice guidance is attempted locally and fails gracefully.
- Events are stored in SQLite.
- JSON and CSV exports are valid.
- Full protocol reaches COMPLETED.

### Camera
- Camera index 0 can be opened when hardware is available.
- Frames are locally processed.
- Annotated frames are available through `/video_feed` on loopback.
- Local MP4 recording can be started/stopped.

### AI extension
- Optional Ultralytics YOLO pose backend can be loaded.
- OpenCV fallback remains usable if heavyweight AI packages are unavailable.
- Dataset collection and model-training scaffolding is included.

## 6. Scientific boundaries

The prototype is not flight-qualified and does not establish microgravity performance. Real deployment would require experiment-specific labeled data, environmental/domain validation, false-alert and missed-step characterization, hardware-in-the-loop testing, edge optimization, and relevant spaceflight/microgravity validation.
