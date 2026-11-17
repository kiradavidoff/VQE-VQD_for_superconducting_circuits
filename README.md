# Benchmarking VQE and VQD for Energy Levels and Transitions in Superconducting Circuits

A Qiskit project investigating ground-state energies, first-excited-state energies and transition frequencies in single and coupled transmon circuits. We compare variational results with classical diagonalization, study controllable numerical choices, and explore IBM Quantum execution.

**Project status:** the main classical simulations have validated saved runs. IBM hardware experiments are exploratory; accurate hardware transition energies have not been demonstrated. Earlier investigations and their results are retained separately.

## Start here

These are the main project entry points. A file's role and validation status are separate: a hardware entry point is not automatically an accurate hardware benchmark.

| Main file | Purpose | Evidence / status |
|---|---|---|
| [Single-transmon simulation](VQE_VQD_Single_Transmon_Simulation.ipynb) | Circuit conversion, charge Hamiltonian, VQE ground refinement, VQD first excited state and transition. | Complete saved classical run; same-model transition agreement below 1 Hz. |
| [Four-transmon simulation and comparisons](VQE_VQD_Four_Transmons_Final.ipynb) | Eight-qubit model; VQE/VQD, initialization, optimizer, truncation, ansatz and coupling studies. | Updated 6.2 GHz model, live summaries and a completed clean-kernel run. |
| [Single-transmon IBM runner](single_transmon_ibm_adam_spsa.py) | Pretrained circuits and angles; Adam-SPSA with measured energies and overlaps. | Automated local checks and recorded `ibm_fez` attempts; hardware accuracy is limited. |
| [Four-transmon IBM notebook](VQE_VQD_Four_Transmons_IBM_ADAM_SPSA.ipynb) | Matching exported operator/circuits; hardware VQE/VQD with Adam-SPSA. | Default plan checked; no recorded four-transmon QPU result. |

See the [file guide](docs/FILE_GUIDE.md) for main, benchmark, recorded-run and archived files, and the [validation record](docs/VALIDATION.md) for what was actually checked.

## What we calculate

- **VQE:** minimize the ground-state energy expectation.
- **VQD:** estimate the first excited state using a penalty against overlap with the prepared ground state.
- **Transition:** subtract physical energies, excluding the artificial VQD penalty.
- **Benchmarks:** compare initial angles, optimizers, charge cutoff, local levels, ansatz cost and penalty strength.
- **Hardware:** assess measured energies, finite-shot uncertainty, overlap-circuit noise and QPU resources.

The circuit model is

$$
H=\sum_i\left[4E_{C,i}(\hat n_i-n_{g,i})^2-E_{J,i}\cos\hat\phi_i\right]
+h\sum_{(i,j)}g_{ij}\hat n_i\hat n_j.
$$

Code energies are divided by $h$ and expressed in GHz; $g_{ij}$ is also in GHz. Angles are radians. The difference of stored eigenvalues directly gives $f_{01}$ in GHz.

Both inductance and an **uncoupled linear** frequency are needed to infer effective capacitance:

$$
C_{\mathrm{eff}}=\frac{1}{L_J(2\pi f_{\mathrm{lin}})^2},\qquad
E_C=\frac{e^2}{2C_{\mathrm{eff}}},\qquad
E_J=\frac{(\hbar/2e)^2}{L_J}.
$$

This is an effective circuit reduction. An EM resonance is not automatically a nonlinear quantum transition. For coupled transmons, $E_1-E_0$ is the **lowest collective transition**, not four individually determined qubit frequencies.

## Representative classical results

| Model | Encoded qubits | Full charge reference $f_{01}$ | VQE/VQD $f_{01}$ | Absolute difference |
|---|---:|---:|---:|---:|
| Single transmon, $N=8$ | 5 | 4.993277878240 GHz | 4.993277878240 GHz | Below 1 Hz |
| Four transmons, $N=9$, four local levels | 8 | 6.199991289025 GHz | 6.200000196732 GHz | 8.908 kHz |

The single-transmon inputs are 10 nH and 5.21015 GHz linear frequency. The current four-transmon configuration uses about 5.8276 nH per site, 93.3125 fF effective capacitance and illustrative 0.10 GHz ring charge-coupling coefficients. Its N=9 to N=10 transition shift is about 0.197 kHz; local-level projection accounts for most of the remaining charge-reference difference.

These are noiseless model comparisons, not experimental precision. The main notebooks include inputs, references, parameter exports and saved outputs. The earlier four-transmon configuration near 4.68325 GHz is preserved with its matching JSON in the [previous-model archive](archive/previous_four_transmon_model/).

## Installation

Use Python 3.11 or later; the core numerical workflows were checked with Python 3.14.0. Numerical/Qiskit versions in `requirements.txt` reproduce the checked core environment.

```bash
git clone https://github.com/kiradavidoff/VQE-VQD_for_superconducting_circuits.git
cd VQE-VQD_for_superconducting_circuits
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
jupyter lab
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`. Install `requirements-experiments.txt` for the additional Plotly benchmark. Archived notebooks may need their original dependencies and conventions.

## Run order

1. Run the single-transmon simulation from top to bottom.
2. Run the four-transmon simulation for the coupled model and comparisons.
3. Run their final export cells after any model change, regenerating the paired `single_transmon_best_parameters.json` and `four_transmon_best_parameters.json` files.
4. Inspect the hardware entry points before submitting jobs.

For the single-transmon runner:

```bash
python single_transmon_ibm_adam_spsa.py --mode plan
```

The default plan submits no jobs. `--mode local` is an offline integration check with ideal statevector energies and ideal finite-shot overlap samples; it is not a device-noise model.

To use IBM hardware, configure a saved account using [IBM's credential instructions](https://quantum.cloud.ibm.com/docs/en/ibm-quantum-compute/save-credentials), then follow the [hardware run guide](docs/single_transmon_ibm_adam_spsa.md). No API key belongs in tracked files. `--mode hardware` submits real jobs. The four-transmon notebook similarly defaults to `config.mode="plan"`; changing it to `"hardware"` enables execution.

**Parameter files belong to a specific circuit and Hamiltonian.** The four-transmon JSON preserves the local-basis Pauli operator. Do not mix the current 16-angle single-transmon preparation with the archived 25-angle prototype, or the archived four-transmon parameters with the current model.

Main figures display inline by default. Requested parameter JSONs are written by the export cells; separate figure/data exports remain controlled by the saving flags.

## Recorded hardware experiments

The [hardware records](results/hardware/README.md) contain a single-transmon warm-start measurement on `ibm_fez` and an incomplete later optimization. The first reported transition was about 0.2155 +/- 0.366 GHz against the 4.9933 GHz model value, with poor self-overlap and substantial padding population. This demonstrates execution and the limitations of the deep circuits, not accurate hardware spectrum recovery. The later run encountered the instance usage limit.

No four-transmon QPU result is recorded. The four-transmon hardware notebook has plan-mode saved output.

## Additional work and checks

- [benchmarks](benchmarks/README.md): additional optimizer/shot/noise experiments, with their distinct assumptions and saved-run status.
- [results](results/README.md): actual hardware records and historical benchmark data.
- [archive](archive/README.md): earlier VQE-only models, alternate formulations and trial notebooks.
- [consolidation record](docs/BRANCH_CONSOLIDATION.md): merged branch histories, conflict resolution and original-file provenance.

All five development branches are included. All 16 distinct notebook versions from their tips remain available byte-for-byte. Archiving does not mean that every older notebook was untested or incorrect.

```bash
python -m unittest discover -s tests -v
python tests/validate_repository.py
```

These automated checks use no IBM account or QPU allocation. They cover circuit/parameter transfer, optimizer behavior, local Runtime APIs, the default four-transmon plan, repository links and archival provenance. They do not rerun every archived experiment or establish hardware accuracy. See [validation details](docs/VALIDATION.md).

## Limitations and next steps

- Classical diagonalization is faster for these small effective Hamiltonians. Full EM simulation and reduced-Hamiltonian diagonalization are different tasks; no quantum speedup is demonstrated.
- Charge cutoff, local-level projection, ansatz and optimization errors need separate checks. Transition errors can conceal cancellation between state-energy errors.
- Coupled-device predictions require calibrated capacitances/couplings and relevant additional modes; the ring coefficients here are illustrative.
- Analytic simulator gradients are classical resources. Hardware Adam-SPSA uses measured perturbations and incurs extra overlap/shot costs.
- Lower circuit depth, shot allocation, noise characterization and additional excited states are the main hardware-development directions.

## Team

Kira Davidoff, Datrim Wadhawan, Benjamin Thomas and Jonathan Martin.

## References

- Koch et al., [Charge-insensitive qubit design derived from the Cooper pair box](https://arxiv.org/abs/cond-mat/0703002).
- Higgott et al., [Variational Quantum Computation of Excited States](https://arxiv.org/abs/1805.08138).
- Leng et al., [Robust and efficient algorithms for high-dimensional black-box quantum optimization](https://arxiv.org/abs/1910.03591).
- IBM [EstimatorV2](https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/0.43/estimator-v2), [SamplerV2](https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/0.43/sampler-v2) and [QPY](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.2/qpy) documentation for the checked versions.
