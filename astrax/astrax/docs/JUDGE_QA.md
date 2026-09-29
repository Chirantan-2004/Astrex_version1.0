# Likely Judge Questions

## Why AI + deterministic rules?
The perception layer is probabilistic. Protocol safety/sequence decisions should be explicit and auditable. Separating the two makes errors explainable and allows the protocol engine to be independently tested.

## Why temporal validation?
A single frame can be noisy. The prototype requires repeated, consistent observations before committing an activity to the protocol state machine.

## Why offline?
The target use case is an onboard assistant where continuous ground connectivity cannot be assumed. The core prototype has no cloud dependency.

## What is trained?
The included dataset tooling supports collection and training of an experiment-specific activity classifier. The judge-safe demo uses deterministic observations so the complete software flow can be demonstrated reliably.

## What is the research limitation?
The current prototype is a terrestrial functional demonstration. Real deployment requires validated spaceflight/microgravity data, domain adaptation, hardware-in-the-loop testing, robustness testing, and formal verification/qualification.

## Why not use an LLM for protocol validation?
An LLM can assist with explanation, but the prototype keeps the safety-relevant state transition deterministic. This reduces ambiguity and makes the decision trace auditable.

## How would it scale?
The perception, activity model, protocol definitions, storage and UI are modular. A new experiment can be represented by a new protocol and experiment-specific model without rewriting the state engine.
