# AcmeCloud — Incident Post-Mortem: March 15, 2026 API Latency

## 1. Incident Overview
* **Date of Event**: March 15, 2026 (14:20 UTC to 16:45 UTC).
* **Impact**: Intermittent HTTP 504 gateway timeouts and elevated API latency affecting North America and Europe regions.
* **Root Cause**: An **overloaded database connection pool** within the core authentication and metadata service caused downstream API request queue starvation during a sudden surge in traffic.

## 2. Data Integrity & Customer Actions
* **Data Loss**: **No customer data was lost or corrupted** during the March 15 incident. All write operations were safely queued or returned transient error codes.
* **Recommended Customer Action**: During API disruptions or transient failures, client SDKs and integrations should **retry failed requests using exponential backoff** with full jitter.
* **Outage Compensation**: AcmeCloud does not offer automatic refunds or standard financial compensation for transient API degradation on non-enterprise tiers unless specifically covered under an Enterprise SLA agreement.
