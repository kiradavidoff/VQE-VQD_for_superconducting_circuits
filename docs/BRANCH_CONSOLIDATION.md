# Branch consolidation

Prepared from the following branch tips. All are ancestors of the consolidation branch; existing development branches are retained.

| Development branch | Included commit |
|---|---|
| `VQE_Simulations_Datrim` | `b7d53b635c350109bdbb7c0f1a4997016f8ae92b` |
| `VQE_VQD_Benji_Datrim_IBM_Quantum_Run` | `a07b9a1d29fa4efc3850beddfdefced6bee419a2` |
| `VQE_VQD_Benji` | `0a593a90fb9645fe40f78556a4b9d2dcf792fd08` |
| `vqd-implementation` | `e8a2e53ea188636fc8bcf47624e9693de698bb26` |
| `vqe-attempt-j` | `9e03e68d08cefaf86ae8cbd7d22652606d531696` |

Base main commit: `179de402fe83881d9a1e7279deeca4c8bba1d4fd`.

## Merge conflict and preservation

The only merge conflict was `VQE_experiments.ipynb`. The optimizer-study version was selected for the merge, then all three unique versions were placed under `archive/variants/`. No notebook version was discarded.

The IBM-run branch already contained the simulation branch, so that history was included through ancestry rather than duplicate commits.

## File curation

- The main entry points remain at the repository root.
- Older notebooks and environment/editor configuration moved into `archive/`.
- The separate single-transmon optimizer benchmark moved into `benchmarks/`.
- Recorded IBM attempts and historical plot/data exports moved into labeled `results/` subfolders.
- The current four-transmon notebook and matching JSON were promoted from the validated 6.2 GHz project update; the prior model is archived intact.
- Mac Finder metadata was removed and local environments/credentials are ignored.

The [manifest](consolidation_manifest.json) provides byte-for-byte original-notebook provenance. Notebook content and data retain their original authors through the merged history.
