# Implementation Plan: Physics-Based V_set & Device Classification System

This plan outlines the implementation of a scientifically rigorous switching analysis and robust classification system for memristor devices, specifically addressing organic polydopamine (PDA) protonic-electronic synapse behaviors.

## Proposed Changes

### 1. Physics-Based $V_{set}$ Extraction (Conduction Regimes)
We replace the current heuristic threshold method (baseline $\times$ 10) with a scientifically rigorous **local log-log derivative method** based on Space-Charge-Limited Current (SCLC) theory:

$$\text{Slope } m = \frac{d\log_{10}|I|}{d\log_{10}|V|}$$

We segment the forward sweep ($0 \to V_{max}$) into distinct physical transport regimes:
* **Ohmic Region**: $m \approx 1$
* **SCLC / Child's Law**: $m \approx 2$
* **Trap-Filled Limit (TFL) / Filamentary Switching ($V_{set}$)**: $m \ge 3$ (spiking to $\ge 4$ at the transition point)

#### Mathematical Implementation in `switching.py`
* Filter forward sweep data for $V > 0.05\text{ V}$ to eliminate near-zero noise.
* Apply a 3-point moving average to smooth the log-current values and reduce derivative noise.
* Compute $m_k = \text{gradient}(\log_{10}|I|, \log_{10}|V|)$.
* Define $V_{set}$ as the first voltage where:
  1. $m_k \ge \theta_{slope}$ (default threshold $\theta_{slope} = 3.0$)
  2. Current $|I_k| > 10\text{ nA}$ (above the instrument's noise floor)
  3. The local derivative $dI/dV$ is positive.

---

### 2. Manual Classifications Override (YAML & CLI)
To ensure absolute control over classification, we propose a two-tiered manual override system that bypasses automated heuristics:

#### Tier A: Persistent Configuration (Protocol YAML)
In `<protocol_name>.yaml`, we support a new `classifications` configuration block:
```yaml
device_overrides:
  materials:
    "cu-c-pda(q)-ito": "volatile"
    "cu-c-pda(q2)-ito": "volatile"
    "cu-c-pda(q3)-ito": "volatile"
  cells:
    "r0c0": "short"
    "r3c2": "insulating"
```

#### Tier B: CLI Overrides
We will extend the `memristor analyze` command to parse override arguments:
`memristor analyze --override-mat "cu-c-pda(q,q2,q3)-ito:volatile" --override-cell "0,0:short"`

The CLI parser will:
1. Parse wildcard patterns (e.g. `cu-c-pda(q*)-ito`) or bracketed expansions (`cu-c-pda(q,q2,q3)-ito`).
2. Write manual designations directly to the SQLite `materials` table.
3. Mark override entries with a clear status `errors = "manual override"`.

---

### 3. Cycle-Level Volatility Tracking
We introduce a **Volatility Yield** ($Y_{vol}$) calculation to analyze cycle-to-cycle stability and capture sweeps where a volatile device gets "stuck" (behaving non-volatilely in specific cycles):

$$\text{Cycle Type} = \begin{cases} 
\text{Volatile} & \text{if } V_{set} \text{ detected and } V_{reset} \text{ is NULL (or } |V_{reset}| < 0.15\text{ V)} \\
\text{Non-Volatile} & \text{if } V_{set} \text{ detected and } V_{reset} \ge 0.15\text{ V}
\end{cases}$$

$$Y_{vol} = \frac{N_{volatile\_sweeps}}{N_{total\_switching\_sweeps}} \times 100\%$$

* **Cell Classification Rules**:
  * $Y_{vol} \ge 80\% \implies$ `volatile` (remark: `"volatile (volatile in X/Y cycles)"`)
  * $20\% \le Y_{vol} < 80\% \implies$ `unstable-volatile` or `volatile` with a warning of mixed behavior.
  * $Y_{vol} < 20\% \implies$ `non-volatile`.

We will update `classify_and_populate_materials` in `db.py` to calculate this metric dynamically using the files table, storing it in the `errors` or a new field, and exposing it to the serving API.

---

## Verification Plan

### Automated Tests
* Run `pytest tests/test_memristor/` to verify database sync remains correct.
* Write a new unit test suite in `tests/test_memristor/test_physics.py` simulating:
  1. Synthetic Ohmic and SCLC IV sweeps to verify transition point extraction accuracy.
  2. Manual classifications lookup and parsing from protocol YAML.
  3. Volatility yield calculations on cells with mixed multicycle sweep data.

### Manual Verification
* Execute `memristor analyze --force` to verify updated physics-based $V_{set}$ calculations across all files.
* Test custom CLI flag parsing:
  `memristor analyze --override-mat "cu-c-pda(q,q2,q3)-ito:volatile"`
  Check that the SQLite `materials` table updates and registers the designation.
