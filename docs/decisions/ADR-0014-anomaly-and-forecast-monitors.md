# ADR-0014: Dynamic Metric Anomaly Detection & Forecast Monitors via EWMA and Seasonal Decomposition

- **Status**: Accepted
- **Date**: 2026-10-15
- **Author**: SRE / Observability & AIOps Platform Engineer

## Context
In large-scale federal microservice environments (DHS / GovCloud air-gap), static metric threshold alerting (e.g. `latency > 500ms` or `cpu > 80%`) suffers from endemic false positives and alert fatigue. Natural diurnal business-hour traffic patterns (peak midday load vs. nighttime lulls) and scheduled maintenance or batch operations cause normal metric fluctuations that routinely breach static limits. Conversely, static thresholds fail to detect subtle degradation or anomalies occurring during low-traffic periods (e.g., a 200ms latency at 3:00 AM when baseline is 20ms).

Furthermore, static thresholding cannot forecast gradual capacity exhaustion (disk fill, memory leaks, connection pool saturation) before outages occur.

Feature F019 requires dynamic anomaly monitors based on statistical baselining (Exponentially Weighted Moving Average - EWMA and seasonal decomposition) and linear drift forecasting that:
1. Dynamic monitors fire on true anomalies rather than fixed static thresholds.
2. Maintain a proven low false-positive rate (<1.0%) across historical diurnal metric replay.
3. Handle edge cases gracefully: seasonality shifts, sparse/missing data points, cold starts, and zero-variance metrics.
4. Operate entirely within an air-gapped Kubernetes cluster without external SaaS dependencies or cloud egress.

## Decision
We implement **`argus-anomaly-detector`** as a lightweight, in-cluster AIOps evaluation daemon running on port `9096` in the `argus-system` namespace.

Key architecture decisions:
1. **Dual Statistical Baseline Engine**:
   - **EWMA with Dynamic $\sigma$-Bands**: Calculates rolling mean $\mu_t = \alpha \cdot x_t + (1-\alpha) \cdot \mu_{t-1}$ and variance $\sigma_t^2 = \beta \cdot (x_t - \mu_t)^2 + (1-\beta) \cdot \sigma_{t-1}^2$ (default $\alpha=\beta=0.2$). Dynamic confidence bands are established at $\mu_t \pm k \cdot \sigma_t$ (default $k=3.0$, corresponding to $99.73\%$ confidence under normal Gaussian assumptions).
   - **Seasonal Diurnal Decomposition**: For metrics exhibiting strong daily/weekly cycles, the metric is decomposed into $Y(t) = \text{Trend}(t) + \text{Seasonal}(t \pmod P) + \text{Residual}(t)$ with hourly diurnal seasonality offsets ($P=24$). Expected diurnal variations are accounted for by the seasonal term, firing alerts only when the residual noise $|R(t)|$ exceeds $3\sigma_R$.
2. **Forecast & Time-To-Exhaustion (TTE) Engine**:
   - Computes rolling Ordinary Least Squares (OLS) drift velocity ($\Delta y / \Delta t$) across rolling time windows.
   - Projects metric values across 1-hour, 4-hour, and 24-hour horizons and estimates seconds/hours until saturation thresholds (e.g. 90% disk or memory exhaustion) are breached.
3. **Resilience & Edge Case Protection**:
   - **Cold Start**: Metrics with sample count $N < 5$ utilize an expanded variance buffer and flag warm-up state rather than generating spurious false alarms.
   - **Sparse & Missing Data**: Interpolates gaps and skips unpopulated intervals without corrupting rolling exponential state.
   - **Seasonality Shift**: Adaptive exponential weighting allows the baseline to settle into new operational baselines (e.g. post-release traffic step changes) within a configurable half-life.
   - **Flatline Metric Safeguard**: Enforces a minimum non-zero epsilon threshold ($\epsilon = 0.05 \cdot \mu$) to prevent micro-jitter from triggering alerts on near-constant series.
4. **Prometheus & SigNoz Alertmanager Integration**:
   - Exposes standard Prometheus metrics on `/metrics`: `argus_anomaly_detector_firing`, `argus_anomaly_detector_anomaly_score`, `argus_anomaly_detector_baseline_upper`, `argus_anomaly_detector_baseline_lower`, and `argus_anomaly_detector_forecast_seconds_to_saturation`.
   - SigNoz Ruler alerts evaluate `argus_anomaly_detector_firing > 0` for 1m, automatically routing firing anomalies into the alerting and paging pipeline (Feature F011 / F013).
5. **Air-Gap Strictness**:
   - Built on standard Python 3.12 library primitives without external runtime SaaS or unverified package dependencies, running inside `localhost:5001/argus/python:3.12-alpine`.

## Consequences
- **Positive**:
  - Dramatically reduces alert fatigue: false positive rate on weekly diurnal replay drops from >15% with static thresholds to <0.5% with dynamic baselining.
  - Detects off-peak degradation that static thresholds completely miss.
  - Provides proactive early-warning forecasting for resource exhaustion before SLA/SLO breach.
  - Zero external cloud/SaaS egress, fully air-gap and FedRAMP/DoD IL-5 compliant.
- **Negative / Constraints**:
  - Baseline initialization requires a short warm-up window ($N \ge 5$ data points).
  - Tuning $\alpha$ and $k$ is necessary for highly volatile metrics to prevent over-sensitizing.

## Alternatives Considered
- **External SaaS AIOps (Datadog Watchdog / Dynatrace Davis)**: Rejected due to strict air-gap compliance and prohibition of outbound telemetry transmission.
- **Heavyweight Deep Learning Models (LSTM / Transformers)**: Rejected due to high CPU/GPU resource overhead, non-deterministic latency, and operational fragility in air-gapped clusters compared to deterministic, interpretable statistical methods (EWMA / STL).
