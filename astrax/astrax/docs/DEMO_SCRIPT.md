# 3-Minute SIH Demo Script

## 0:00 — Mission setup
"ASTRAX is a local-first experiment supervisor. It watches an experiment, recognizes the current activity, compares it with the protocol, guides the astronaut, and records the event."

## 0:20 — Start
Click **Start / Restart Demo**.

Show the protocol moving from READY to RUNNING.

## 0:35 — Correct action
Click **Next Correct Step** twice.

Point to:
- detected activity
- confidence
- verified protocol step
- next action
- timestamped event

## 1:10 — Inject error
Click **Inject Wrong Step**.

Say:
"The AI perception may identify an action, but the deterministic protocol engine decides whether that action is valid for the current experiment state."

Show:
- expected action
- detected action
- protocol violation
- guidance message
- voice alert if pyttsx3 is installed

## 1:45 — Recover
Click **Next Correct Step** until completion.

Show green verified states and completion message.

## 2:20 — Structured memory
Open Export JSON or CSV.

Explain that each event contains timestamp, step, expected/detected activity, confidence, status and message.

## 2:40 — Edge/offline
Toggle Offline and point to the OFFLINE badge.

Say:
"The core demonstration does not require a cloud API. Production deployment can move the perception models to an edge computer such as a Jetson-class device."

## 2:55 — Closing
"The prototype demonstrates the complete loop from observation to protocol-aware action validation, guidance, and experiment memory. The next research stage is experiment-specific dataset collection and validation under relevant spaceflight conditions."
