# Walkthrough: SCLC Physics & Device Override System

We have successfully designed, implemented, and fully tested a highly precise, scientifically grounded switching analysis and device classification system for organic memristors.

## 🚀 Accomplishments

### 1. Physics-Based $V_{set}$ Extraction (SCLC Theory)
We replaced the previous $10\times$ baseline current threshold heuristic with a local log-log slope calculation in [switching.py](file:///Users/tai/workspace/tools/science-cli/src/science_cli/library/memristor/switching.py).
* **Mathematical Formula**:
  $$\text{Slope } m_k = \frac{\log_{10}|I_k| - \log_{10}|I_{k-1}|}{\log_{10}|V_k| - \log_{10}|V_{k-1}|}$$
* **Conduction Transport Identification**:
  * Ohmic region: $m \approx 1$
  * Space-Charge-Limited Current (Child's law): $m \approx 2$
  * Trap-Filled Limit / Filamentation switching: $m \ge 3$
* **Denoising**: Added 3-point moving-average smoothing on log-current values before computing gradients to suppress measurement and derivative noise.
* **Extraction**: $V_{set}$ is triggered at the first forward positive sweep point where $m \ge 3.0$ and current magnitude is above the instrument noise floor ($|I| > 10\text{ nA}$).

### 2. Manual Classifications Override with Bracket Expansion
We implemented support for persistent, repeatable manual overrides that completely bypass automated classification heuristics:
* **Persistent Configuration (Tier A)**: Added support for a new `device_overrides` section inside the protocol YAML:
  ```yaml
  device_overrides:
    materials:
      "cu-c-pda(q)-ito": "volatile"
      "cu-c-pda(q2)-ito": "volatile"
      "cu-c-pda(q3)-ito": "volatile"
    cells:
      "r0c0": "short"
  ```
* **Dynamic CLI Designations (Tier B)**: Updated [device_cli.py](file:///Users/tai/workspace/tools/science-cli/src/science_cli/library/memristor/device_cli.py) to support override flags and custom expressions:
  `memristor analyze --mat cu-c-pda(q,q2,q3)-ito is volatile`
* **Cluster Parsing**: Wrote an automatic bracket expansion parser resolving `"cu-c-pda(q,q2,q3)-ito"` into three individual material strings.
* **Tier B Writes to Tier A**: CLI overrides now automatically update the protocol's YAML file permanently, ensuring reproducibility!

### 3. Dynamic Volatility Yield Tracking
Instead of a simple binary classification, we introduced dynamic cycle-to-cycle tracking in [db.py](file:///Users/tai/workspace/tools/science-cli/src/science_cli/library/memristor/db.py):
* **Bipolar Cycles**: We classify a sweep cycle as volatile if $V_{set}$ is detected and the spontaneous relaxation voltage is negligible ($|V_{reset}| < 0.15\text{ V}$ or reset is NULL).
* **Volatility Yield**:
  $$Y_{vol} = \frac{N_{volatile\_sweeps}}{N_{total\_switching\_sweeps}} \times 100\%$$
* **High-Fidelity Remarks**: The cell coordinate is automatically classified and logs its cycle yield directly in the database (e.g. `relaxation profile (8/10 cycles volatile)` or `mixed volatility: 60.0% (6/10 cycles volatile)`).

---

## 🧪 Verification & Health Results

1. **New Unit Tests**: Created [test_physics.py](file:///Users/tai/workspace/tools/science-cli/tests/test_memristor/test_physics.py) verifying:
   * SCLC slope-based transition trigger on synthetic SCLC I-V curves.
   * Bracket cluster pattern parsing and expansions.
   * Dynamically calculated volatility yields on cells holding multiple sweeps.
2. **Repository Guardrails**: Resolved a missing gitignored `AGENTS.md` index file, making the workspace test suite fully green.
3. **Execution Run**:
   ```bash
   pytest
   ```
   **Result**: `103 passed in 0.90s` (100% green).
