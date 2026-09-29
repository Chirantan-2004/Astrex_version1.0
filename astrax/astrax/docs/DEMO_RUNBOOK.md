# ASTRAX — Judge Demo Runbook

## Goal
Demonstrate the full loop without depending on network access or a fragile live ML model.

## 90-second flow
1. Open the dashboard.
2. Point out `EDGE / LOCAL`, `SQLITE`, and `TEMPORAL + RULES`.
3. Click **Start Demo**.
4. Click **Correct Step** three-to-five times to advance the protocol.
5. Before the next expected step, click **Inject Error**.
6. Show the red `PROTOCOL VIOLATION` panel: expected vs detected and recommended action.
7. Explain that the AI proposes an activity while the deterministic protocol engine decides whether that activity is valid in the current state.
8. Continue with **Correct Step** until `EXPERIMENT COMPLETE`.
9. Export JSON and CSV.
10. If the camera works, start it and show the LAN `/video_feed` endpoint; otherwise keep the deterministic demo as the primary judge path.

## The one sentence to remember
> ASTRAX does not merely recognize an action; it evaluates that action in the context of the experiment protocol and creates an auditable mission event.

## Do not claim
- Microgravity validation
- Flight qualification
- Mission-critical certification
- Official BAS procedure coverage
- Accuracy on a representative astronaut dataset unless measured and documented

## Recovery
If camera/AI packages fail, do not stop the demo. Demo Mode is intentionally independent of the optional perception stack.
