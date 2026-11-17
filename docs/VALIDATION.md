# Validation and result status

## Classical calculations

The main single-transmon notebook stores a full calculation for the 10 nH, 5.21015 GHz linear-input model. Its refined VQE/VQD transition agrees with exact charge diagonalization at the same cutoff to below 1 Hz. This is numerical model agreement.

The promoted four-transmon notebook is the updated model checked from a clean kernel during project development. It uses about 5.8276 nH per site, 93.3125 fF, cutoff 9 and four local levels. Its saved transition is 6.200000196732 GHz versus 6.199991289025 GHz full-charge reference: 8.908 kHz difference. The N=9 to N=10 shift is about 0.197 kHz. Live summaries replace the old fixed example numbers.

The notebooks check state energies, truncation/projection, Pauli reconstruction, parameter mapping and overlap. A small transition error can conceal cancellation between state-energy errors. Noiseless agreement is not experimental precision.

## Automated checks

```bash
python -m unittest discover -s tests -v
python tests/validate_repository.py
```

Checks cover parameter order/QPY transfer; model consistency; Adam-SPSA updates; VQD cost selection; finite-shot boundary uncertainty; the single-transmon local pipeline; real Runtime V2 interfaces against a local backend; the default four-transmon plan with account/primitive construction blocked; notebook/JSON structure; documentation links; and archival provenance.

No credentials or QPU allocation are used. CI is configured for these checks; its hosted pass/fail result is determined after publication. The suite does not rerun every archived notebook or establish hardware accuracy.

## Hardware and historical studies

The [ibm_fez records](../results/hardware/README.md) show real execution with poor spectrum recovery. A later optimizer attempt reached the instance usage limit and has no final transition in its checkpoint. No four-transmon QPU result is recorded.

The additional single-transmon benchmark has saved execution counts for 10/12 code cells. Its exact-ground reference and simplified noise assumptions differ from actual hardware VQD.

The archived Open Plan prototype expects `step1_noiseless_vqe_parameters.json`, absent from the merged branches. It uses 25 angles and another wire convention; do not substitute the current 16-angle JSON. The archived alternative Fock-basis notebook also contains edited parameter/dimension conventions needing review before reuse. Preservation is not a certification of all historical code.
