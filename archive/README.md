# Archive: earlier notebooks and trial runs

This folder preserves the original notebooks from every merged branch. They are development history rather than the main starting workflow. Archival status does not imply that a notebook was never tested.

| File | Original branch(es) | Saved executed/code cells |
|---|---|---:|
| [notebooks/VQE_Coupled_Transmon.ipynb](notebooks/VQE_Coupled_Transmon.ipynb) | VQE_Simulations_Datrim, VQE_VQD_Benji_Datrim_IBM_Quantum_Run | 14/15 |
| [notebooks/VQE_Four_Coupled_Transmons.ipynb](notebooks/VQE_Four_Coupled_Transmons.ipynb) | VQE_Simulations_Datrim, VQE_VQD_Benji_Datrim_IBM_Quantum_Run | 17/17 |
| [notebooks/VQE_Four_Transmons_Comparisons.ipynb](notebooks/VQE_Four_Transmons_Comparisons.ipynb) | VQE_Simulations_Datrim, VQE_VQD_Benji_Datrim_IBM_Quantum_Run | 38/38 |
| [notebooks/VQE_Single_Transmon.ipynb](notebooks/VQE_Single_Transmon.ipynb) | VQE_Simulations_Datrim, VQE_VQD_Benji_Datrim_IBM_Quantum_Run | 14/14 |
| [previous_four_transmon_model/VQE_VQD_Four_Transmons_Final.ipynb](previous_four_transmon_model/VQE_VQD_Four_Transmons_Final.ipynb) | VQE_Simulations_Datrim, VQE_VQD_Benji_Datrim_IBM_Quantum_Run | 25/25 |
| [variants/main/VQE_experiments.ipynb](variants/main/VQE_experiments.ipynb) | VQE_Simulations_Datrim, VQE_VQD_Benji_Datrim_IBM_Quantum_Run, vqe-attempt-j, main | 8/9 |
| [hardware/IBM_Open_Plan_Transmon_VQE.ipynb](hardware/IBM_Open_Plan_Transmon_VQE.ipynb) | VQE_VQD_Benji_Datrim_IBM_Quantum_Run | 0/9 |
| [hardware/test_IBM.ipynb](hardware/test_IBM.ipynb) | VQE_VQD_Benji_Datrim_IBM_Quantum_Run | 2/4 |
| [notebooks/VQE_VQD_EPR_Transmon_ADS.ipynb](notebooks/VQE_VQD_EPR_Transmon_ADS.ipynb) | VQE_VQD_Benji | 15/15 |
| [variants/VQE_VQD_Benji/VQE_experiments.ipynb](variants/VQE_VQD_Benji/VQE_experiments.ipynb) | VQE_VQD_Benji | 8/9 |
| [variants/vqd-implementation/VQE_experiments.ipynb](variants/vqd-implementation/VQE_experiments.ipynb) | vqd-implementation | 26/29 |
| [notebooks/transmon_vqe_vqd.ipynb](notebooks/transmon_vqe_vqd.ipynb) | vqd-implementation | 11/11 |
| [notebooks/VQE_transmon_LBFGSB_v2.ipynb](notebooks/VQE_transmon_LBFGSB_v2.ipynb) | vqe-attempt-j | 13/13 |

## Before reusing an archived notebook

- Saved outputs can predate edits. A saved execution count is not a fresh-kernel reproducibility guarantee.
- Working-directory assumptions and dependencies are retained from the original files. Relative export paths may need adjustment after relocation.
- The Open Plan VQE prototype requires an absent `step1_noiseless_vqe_parameters.json` and a different 25-angle circuit.
- The shared experiment notebook has three preserved versions, including one that differs only in kernel metadata.
- The previous four-transmon model and JSON belong together; they give a transition near 4.68325 GHz, not the current 6.2 GHz configuration.

Original Git blobs and locations are in the [manifest](../docs/consolidation_manifest.json). The [main README](../README.md) identifies the current entry points.
