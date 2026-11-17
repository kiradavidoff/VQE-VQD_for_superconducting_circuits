# Additional optimizer benchmark

[VQE_VQD_Optimizer_Noise_Benchmark.ipynb](VQE_VQD_Optimizer_Noise_Benchmark.ipynb) is an additional single-transmon study from `vqd-implementation`.

It compares COBYLA, Nelder-Mead, SPSA and Adam with SPSA gradient estimates for a 25-angle RY/CX ansatz, using exact expectations, finite-shot Pauli samples and a simplified noise emulator. This differs from the 16-angle physical-charge refinement in the main single-transmon workflow.

**Recorded status:** 10 of 12 code cells have saved execution counts, with no saved error output. This is not a completed clean-kernel validation of every benchmark cell. Its [exported results](../results/benchmarks/transmon_optimizer_results.json) are retained separately.

Install `requirements-experiments.txt` from the repository root, then open this notebook in Jupyter. It writes its optional export beside the notebook.

The VQD benchmark uses an exact ground reference to isolate optimizer behavior. Its noise and shot accounting do not include the full cost of preparing an approximate VQE reference and measuring compute-uncompute overlaps on a real device. Do not substitute these angle vectors into the main parameter JSON.

The older four-transmon study is in the [archive](../archive/notebooks/VQE_Four_Transmons_Comparisons.ipynb), with [historical data](../results/legacy_four_transmon_benchmarks/README.md). Current four-transmon VQE/VQD comparisons are in the [main notebook](../VQE_VQD_Four_Transmons_Final.ipynb).
