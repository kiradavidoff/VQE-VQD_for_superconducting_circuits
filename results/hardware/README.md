# IBM Quantum experiment records

These files came from `VQE_VQD_Benji_Datrim_IBM_Quantum_Run`:

- [ibm_fez_run_notes.txt](ibm_fez_run_notes.txt): terminal notes for a warm-start measurement and later optimization.
- [single_transmon_ibm_results.json](single_transmon_ibm_results.json): later-run checkpoint with `status="running"`, 14 jobs, 13 marked completed and one submitted. It has no final excited-state result or final transition.

The first run prepared the single-transmon classical warm starts on `ibm_fez`. Its preparations had 834/853 two-qubit gates; compute-uncompute had 1,699. The reported transition was about 0.2155 +/- 0.366 GHz (statistical), versus the model's 4.9933 GHz. Self-overlap was about 0.01465, where the ideal value is one, and more than half the measured population was in padding states. These results do not recover the model spectrum. Small observed cross-overlap under this noise is not evidence of true orthogonality.

The second run requested five Adam-SPSA steps per state. Terminal notes report the instance usage limit was reached. `status="running"` is the saved checkpoint state, not a claim that a process is still active or that the experiment completed.

No four-transmon QPU result is recorded. Future experiments should have separate run names, settings, backend and completion status.
