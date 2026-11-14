# Single-transmon VQE/VQD on IBM Quantum with Adam-SPSA

`single_transmon_ibm_adam_spsa.py` loads the JSON produced by the notebook's export cell, including both complete logical circuits and the best saved ground/excited angle vectors. It follows the same map, transpile, execute and post-process sequence as the classical notebook.

The hardware path uses measured energy expectations and measured compute-uncompute probabilities. Adam-SPSA runs on the classical computer and updates the angles; the quantum processor supplies its objective measurements. No statevector or analytic simulation gradient is used by the hardware objective.

## Files and installation

Put the Python file and your **own** `single_transmon_best_parameters.json` in the same working directory. The script does not substitute test parameters if your file is absent.

The supplied requirements reproduce the tested environment: Python 3.14.0, Qiskit 2.2.3, Runtime 0.43.1, NumPy 2.3.4, SciPy 1.16.3, and Matplotlib 3.10.7. The requirements support Python 3.11 or later, subject to platform package availability.

```bash
python -m pip install -r requirements_single_transmon_ibm.txt
```

The implementation uses the explicit Runtime `EstimatorV2`/`SamplerV2` APIs available in this tested version. IBM's newer documentation also describes newer client-side primitive implementations; this script does not require those experimental interfaces. QPY should be read with a Qiskit version compatible with the version that created the export.

## Inspect before executing

```bash
python single_transmon_ibm_adam_spsa.py --mode plan
```

This default mode loads and validates the input, checks physical conversions, reconstructs the Hamiltonian, transpiles the circuits, and prints depths and two-qubit gate counts. It submits **no jobs**, needs **no IBM account**, and writes no results file. Its generic line target is an offline estimate, not an actual IBM processor.

For an actual-device compilation without submitting jobs, add `--backend` followed by a backend name accessible to your saved IBM account. An optional `--initial-layout` accepts comma-separated physical qubit indices.

The unchanged five-qubit ansatz is deep: the offline inspection of the supplied circuit family gave roughly 1,017/1,022 two-qubit gates for ground/excited preparation and 2,019 for compute-uncompute at optimization level 1. Actual-device compilation can differ. Preserving the original ansatz makes the angles transferable, but does not establish achievable hardware accuracy.

## Check the JSON locally

```bash
python single_transmon_ibm_adam_spsa.py --mode local --ground-steps 0 --excited-steps 0
```

This checks the warm-start circuits using ideal statevector energy calculations and finite-shot ideal overlap samples. It is an offline integration check, **not a device-noise model**. Exact energy standard errors are zero in this mode; they are not a prediction of hardware uncertainty.

To test the optimization loop locally, use positive step counts, for example `--ground-steps 5 --excited-steps 5`. The classical warm starts can already be optimal, so further optimization need not improve them.

The local five-qubit check reproduced the expected transition of approximately **4.993277878 GHz** for the exported single-transmon model. This was not measured on a QPU.

## Run on an IBM processor

Set up credentials separately using IBM's [saved-account instructions](https://quantum.cloud.ibm.com/docs/en/ibm-quantum-compute/save-credentials). The script calls `QiskitRuntimeService()` or loads the optional named profile supplied with `--account`; it does not request, embed, print or save an API key.

Start with measurement of the classical warm starts:

```bash
python single_transmon_ibm_adam_spsa.py --mode hardware --ground-steps 0 --excited-steps 0 --shortlist 1 --final-repeats 1 --shots 1024 --validation-shots 4096
```

This command **submits real jobs**. Zero optimizer steps still require baseline, selection, final-readout, overlap, self-overlap and charge-population measurements. Without `--backend`, the script selects an operational least-busy real processor with enough qubits. A named backend can be selected with `--backend`.

After assessing those measurements, an example small optimization run is:

```bash
python single_transmon_ibm_adam_spsa.py --mode hardware --ground-steps 5 --excited-steps 5 --shortlist 2 --final-repeats 1 --shots 2048 --validation-shots 4096
```

The program uses **job mode**, so it does not require session entitlement. Job-mode queue delays can dominate the run. `--max-job-seconds` sets a per-job QPU-time cap (default 300 seconds); it is not a total experiment limit or a completion guarantee. Large batches, deep circuits, higher shots and mitigation increase resource use.

## What the script does

1. Loads the two logical state-preparation circuits, parameter names and angles from the exported JSON. Reorders values by parameter name after transpilation.
2. Reconstructs the physical charge Hamiltonian with the saved offset charge, cutoff and effective energy parameters. Uses the saved elevated padding energy and asserts Pauli reconstruction.
3. Checks the single-mode conversion from inductance and **linear** frequency. For the notebook defaults: 10 nH, 5.21015 GHz, effective capacitance 93.3125 fF, and five qubits for 17 physical charge states.
4. Calculates exact charge eigenvalues and an enlarged-cutoff transition as validation references. These values never choose optimizer angles or shortlisted candidates.
5. Compiles state-preparation circuits for the selected backend, applies each layout to the Hamiltonian, and reuses the ground circuit's initial physical-qubit mapping.
6. Runs ground-state VQE with Adam-SPSA using measured energy costs.
7. Independently remeasures a shortlist of candidates. Always includes the original warm start and keeps it unless an alternative resolves an improvement using the configurable uncertainty guard.
8. Freezes the selected ground **circuit parameters**, builds the excited/ground compute-uncompute circuit, and runs VQD with measured physical energy plus the measured overlap penalty.
9. Selects excited parameters by independently remeasured **deflated cost**, not by raw energy or agreement with exact diagonalization.
10. Makes fresh energy and overlap measurements after selection. Computes the transition from physical energies, excluding the artificial VQD penalty.
11. Measures ground self-overlap as an overlap-circuit noise diagnostic and measures charge distributions/padding population for both states.
12. Saves the selected circuit parameters, job IDs, histories, measurement uncertainties and reference comparisons to one results JSON. Optional plots display only; no figure files are saved.

## Adam-SPSA and selection details

For each step and each Rademacher direction, all angle-gradient components are estimated from two objective values:

$$\widehat g_k=\frac{F(\theta_k+c_k\Delta_k)-F(\theta_k-c_k\Delta_k)}{2c_k}\Delta_k,
\qquad \Delta_{k,j}\in\{-1,+1\}.$$

The estimate drives bias-corrected Adam moments with beta1 = 0.9, beta2 = 0.999 and epsilon = 1e-8. Defaults use learning rate $0.01/k^{0.1}$, perturbation $0.05/k^{0.101}$ radians and a 0.05-radian update-norm cap. `--resamplings` averages independent directions. These are configurable demonstration settings, not a claimed hardware optimum or exact reproduction of a paper's benchmark.

Two objective values are **not** two total QPU shots or circuits. Each energy expectation can require several measurement configurations. Each VQD objective also needs overlap samples. Perturbation pairs are batched into a PUB to reduce submissions.

The candidate shortlist is chosen from warm-start, SPSA-probe and checkpoint measurements. Higher-shot independent remeasurement reduces noisy-minimum bias. `--selection-sigma` defaults to 2: candidates must improve on the warm start by more than this multiplier of their combined estimated uncertainty. This is a practical guard, not a formal confidence test after multiple comparisons. `--selection-sigma 0` selects the lowest remeasured mean without that guard. The final readout is independent of selection.

## Output and interpretation

Local and hardware runs checkpoint `single_transmon_ibm_results.json` by default. Change it with `--output`. The input JSON is never overwritten. Submitted job IDs are checkpointed before waiting for results; failures are recorded and paid jobs are not automatically resubmitted.

Selected angles and their circuits appear in `ground_parameters` and `excited_parameters`. The output is a results schema, not an automatic replacement for the original warm-start input schema.

`final.transition_GHz` is E1/h minus E0/h; no extra Planck constant or factor of 2*pi is needed. Its statistical uncertainty combines the two energy uncertainties assuming independent sampling. Repeat-based energy uncertainty uses the larger of the propagated reported errors and the observed repeat standard error. Overlap intervals use Wilson intervals; the scalar overlap uncertainty is their half-width divided by 1.96. Neither accounts fully for systematic gate/readout errors or device drift.

On noisy hardware, the all-zero compute-uncompute probability is not an unbiased true-state overlap. Self-overlap should ideally equal one; poor self-overlap shows that this measurement is strongly distorted. No simple normalization or clipping is applied to disguise that effect. Charge populations and padding probabilities are likewise raw readout diagnostics, with no postselection or renormalization.

A small measured overlap or a completed run does not establish that the first excited state was found. Assess individual energy errors, transition error, uncertainty, self-overlap and padding together. The extremely small optimization error from the classical notebook is not a hardware-accuracy claim. Neither least-busy selection nor Adam-SPSA guarantees convergence.

Use `--plot` to display energy/cost, overlap, transition and charge-distribution plots. No separate images are written. Use `--help` for all controls.

## Verification performed

- JSON/circuit loading, reordered parameter binding, physical conversion and Pauli checks.
- Adam-SPSA updates on a known objective, and VQD selection that rejects low-energy ground contamination.
- End-to-end ideal local VQE/VQD, overlap, self-overlap, padding, result export and job logging.
- Actual installed Runtime V2 primitives executed against a local `GenericBackendV2` using IBM's local-testing path. No account or QPU connection was used.
- A five-qubit run using the exported circuit family and the notebook's physical parameters.

**Actual IBM QPU execution has not been performed.** Credentials, backend availability, account limits, hardware compilation and attainable accuracy must be evaluated in your environment.

## Sources

- IBM [EstimatorV2 API for the tested Runtime version](https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/0.43/estimator-v2): backend mode, PUB parameter batching and observable layouts.
- IBM [SamplerV2 API for the tested Runtime version](https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/0.43/sampler-v2): measurement PUBs and shot-based counts.
- IBM [primitive shot/options precedence](https://quantum.cloud.ibm.com/docs/en/ibm-quantum-compute/estimator-options): why fixed shots are configured on Estimator rather than passed as a `shots` argument to its `run` method.
- IBM [session availability and execution modes](https://quantum.cloud.ibm.com/docs/en/ibm-quantum-compute/run-jobs-session): why this script uses job mode by default.
- Leng et al., [Robust and efficient algorithms for high-dimensional black-box quantum optimization](https://arxiv.org/abs/1910.03591): randomized perturbation estimates combined with adaptive momentum.
- Kingma and Ba, [Adam: A Method for Stochastic Optimization](https://arxiv.org/abs/1412.6980): adaptive moments and bias correction.
- Higgott et al., [Variational Quantum Computation of Excited States](https://arxiv.org/abs/1805.08138): overlap-based variational deflation and compute-uncompute overlap estimation.
- IBM [QPY serialization](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.2/qpy): preservation of circuits and parameters across environments. The loader narrowly filters the Qiskit 2.2 warning about unused vector elements inside nested controlled-RY definitions, while checking the complete active parameter set.
