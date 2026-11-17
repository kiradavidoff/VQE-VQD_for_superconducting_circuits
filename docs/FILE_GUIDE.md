# File guide: main workflows and tested experiments

**Main** describes a file's role; **tested** describes the evidence. They are separate labels.

| File | Role | Evidence / status |
|---|---|---|
| [Single-transmon simulation](../VQE_VQD_Single_Transmon_Simulation.ipynb) | Main simulation and export. | Complete saved execution and exact-model comparison. |
| [Four-transmon simulation](../VQE_VQD_Four_Transmons_Final.ipynb) | Main coupled simulation and comparisons. | Updated 6.2 GHz model checked from a clean kernel; live results. |
| [Single-transmon IBM runner](../single_transmon_ibm_adam_spsa.py) | Main hardware entry point. | Local automated tests; actual IBM attempts inaccurate/incomplete. |
| [Four-transmon IBM notebook](../VQE_VQD_Four_Transmons_IBM_ADAM_SPSA.ipynb) | Main hardware entry point. | No-submission plan checked; no recorded four-transmon QPU result. |
| [Single-transmon parameters](../single_transmon_best_parameters.json) | Main circuit/model transfer. | Physical-charge ansatz; not interchangeable with the 25-angle prototype. |
| [Four-transmon parameters](../four_transmon_best_parameters.json) | Main circuit/Pauli transfer. | Matching current model and local eigenbasis. |
| [Additional optimizer benchmark](../benchmarks/README.md) | Secondary experiment. | Partial saved execution; exact-ground VQD reference and simplified noise. |
| [Hardware records](../results/hardware/README.md) | Experiment evidence. | Real execution records, including limitations and interruption. |
| [Legacy benchmark data](../results/legacy_four_transmon_benchmarks/README.md) | Historical outputs. | Older VQE-only configuration. |
| [Automated tests](../tests/) | Repeatable repository checks. | No IBM account/QPU required. |
| [Archive](../archive/README.md) | Development record. | Evidence varies by notebook; not the maintained starting workflow. |

Saved execution counts establish that outputs were recorded, not that edited source has passed a fresh-kernel run. Every one of the 16 distinct incoming notebook versions is retained byte-for-byte. The [manifest](consolidation_manifest.json) maps exact original blobs, branches and new locations.
