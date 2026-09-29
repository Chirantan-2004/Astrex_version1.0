# ASTRAX Architecture

```text
Fixed Camera / Video File
        |
        v
+-----------------------+
| VideoService / OpenCV |
+-----------+-----------+
            |
            v
+-------------------------------+
| VisionEngine                  |
| - YOLO pose (optional)        |
| - OpenCV color/motion fallback|
| - hand/object interaction     |
+---------------+---------------+
                |
                v
+-------------------------------+
| Activity Recognition          |
| - experiment model hook       |
| - temporal confidence filter  |
+---------------+---------------+
                |
                v
+-------------------------------+
| Deterministic Protocol Engine |
| expected -> observed -> state |
+-----------+---------+---------+
            |         |
            |         +--> voice guidance
            |
            +------------> SQLite event memory
                              |
                              +--> JSON / CSV
                              +--> experiment video
                              +--> mission dashboard
```

## Design principle
AI perception may be uncertain. Protocol validation must be explicit. The prototype therefore keeps the two layers separate.

## Identity and communication boundaries
- OIDC discovery/code flow is configured by environment variables; sessions use signed, HttpOnly, SameSite=Lax cookies and Secure cookies behind HTTPS.
- Protected mission APIs fail closed if OIDC is absent. The local demo bypass is opt-in and must remain bound to loopback.
- Crew uplinks persist as `QUEUED_LOCAL`. There is no remote ground relay yet; local queue state is never shown as delivered.
- Camera observations carry monotonic timestamps. Three distinct, consecutive, sufficiently confident observations inside the one-second window are required to change protocol state. Stale or idle evidence holds or clears consensus.

## Deployment path
Laptop prototype → ONNX/TensorRT optimization → Jetson-class edge hardware → hardware-in-the-loop validation → relevant environmental/spaceflight validation.
