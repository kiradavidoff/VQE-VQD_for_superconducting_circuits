#!/usr/bin/env python3
"""Single-transmon VQE/VQD with JSON warm starts and Adam-SPSA.

Run ``python single_transmon_ibm_adam_spsa.py --help`` for options.
Default mode is an offline plan: it submits no jobs and needs no IBM account.
``--mode hardware`` explicitly runs IBM Quantum jobs using saved credentials.

Follows the notebook: map -> transpile -> execute -> post-process. All energy
numbers are E/h in GHz, angles are radians, and n counts excess Cooper pairs.
Hardware objectives use Runtime measurements, never statevectors or analytic
simulation gradients. NumPy diagonalization is only a validation reference.

Research/API references and tested versions are in the companion README.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import importlib.metadata
import io
import json
import math
from pathlib import Path
from time import perf_counter
import warnings

import numpy as np
from scipy.constants import e as electron_charge, h as planck_h
from qiskit import QuantumCircuit, qpy
from qiskit.primitives import StatevectorEstimator, StatevectorSampler
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit.quantum_info import Operator, SparsePauliOp
from qiskit.transpiler import CouplingMap
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager


def write_json(path: Path, data: dict) -> None:
    """Checkpoint one results file, without writing figures or credentials."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def versions() -> dict:
    result = {}
    for name in ("qiskit", "qiskit-ibm-runtime", "numpy", "scipy"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "not installed"
    return result


@dataclass
class WarmState:
    circuit: QuantumCircuit
    angles: np.ndarray
    names: list[str]

    def values_for(self, circuit: QuantumCircuit, points: np.ndarray) -> np.ndarray:
        """Reorder logical angles to the actual transpiled parameter order."""
        if {p.name for p in circuit.parameters} != set(self.names):
            raise ValueError("Transpilation changed the circuit parameter set.")
        indices = [self.names.index(p.name) for p in circuit.parameters]
        return np.asarray(points, dtype=float)[:, indices]

    def bound(self, angles: np.ndarray) -> QuantumCircuit:
        by_name = dict(zip(self.names, angles))
        return self.circuit.assign_parameters({p: by_name[p.name] for p in self.circuit.parameters})

    def export(self, angles: np.ndarray) -> dict:
        buffer = io.BytesIO()
        qpy.dump(self.circuit, buffer)
        return {
            "parameter_order": self.names,
            "parameters_rad": np.asarray(angles, dtype=float).tolist(),
            "logical_circuit_qpy_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
        }


def load_warm_starts(path: Path) -> tuple[dict, WarmState, WarmState]:
    """Load the Cell 1 JSON and preserve both circuit definitions exactly."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Expected schema_version=1 from the notebook export cell.")
    states = []
    for label in ("ground", "excited"):
        entry = data[label]
        names = entry["parameter_order"]
        angles = np.asarray(entry["parameters_rad"], dtype=float)
        with warnings.catch_warnings():
            # Qiskit 2.2 warns about *unused* vector elements inside each c_ry
            # definition. Validate the full active parameter set below instead.
            warnings.filterwarnings(
                "ignore", message=r"The ParameterVector:.*weren't used in the circuit: c_ry",
                category=UserWarning, module=r"qiskit\.qpy\.binary_io\.circuits",
            )
            circuits = qpy.load(io.BytesIO(base64.b64decode(entry["logical_circuit_qpy_base64"], validate=True)))
        if len(circuits) != 1:
            raise ValueError(f"Expected one {label} logical circuit.")
        circuit = circuits[0]
        if angles.shape != (len(names),) or not np.all(np.isfinite(angles)):
            raise ValueError(f"Invalid {label} angle vector.")
        if len(names) != len(set(names)) or set(names) != {p.name for p in circuit.parameters}:
            raise ValueError(f"{label} parameter names do not match its circuit.")
        if circuit.num_clbits or any(x.operation.name in {"measure", "reset"} for x in circuit.data):
            raise ValueError("Warm-start circuits must contain unitary state preparation only.")
        states.append(WarmState(circuit, angles, names))
    return data, states[0], states[1]


# 3.1 Step 1: map the charge model to operators and use the exported ansätze.
def build_model(data: dict, ground: WarmState, excited: WarmState) -> tuple[dict, SparsePauliOp]:
    model = data["model"]
    raw_n = model["charge_cutoff_N"]
    if isinstance(raw_n, bool) or int(raw_n) != raw_n or raw_n < 1:
        raise ValueError("Charge cutoff N must be a positive integer.")
    cutoff = int(raw_n)
    charge = np.arange(-cutoff, cutoff + 1)
    dimension = len(charge)
    qubits = (dimension - 1).bit_length()
    ec = float(model["E_C_over_h_GHz"])
    ej = float(model["E_J_over_h_GHz"])
    ng = float(model["n_g"])
    padding = float(model["padding_energy_GHz"])
    beta = float(model["beta_GHz"])
    if not np.all(np.isfinite([ec, ej, ng, padding, beta])) or min(ec, ej, beta) <= 0:
        raise ValueError("Invalid Hamiltonian parameters or VQD penalty.")
    if model["num_qubits"] != qubits or model["physical_dimension"] != dimension:
        raise ValueError("Saved charge dimensions and qubit count disagree.")
    if ground.circuit.num_qubits != qubits or excited.circuit.num_qubits != qubits:
        raise ValueError("Circuit width differs from the saved charge encoding.")
    if len(ground.angles) != dimension - 1 or len(excited.angles) != dimension - 1:
        raise ValueError("Expected the section 4 physical-charge ansatz with d-1 angles.")

    # Use both L and the *linear* frequency; L alone cannot determine capacitance.
    inductance = float(model["L_J_nH"]) * 1e-9  # [H].
    frequency = float(model["f_linear_GHz"]) * 1e9  # [Hz].
    if not np.all(np.isfinite([inductance, frequency])) or min(inductance, frequency) <= 0:
        raise ValueError("Inductance and linear frequency must be positive.")
    capacitance = 1 / (inductance * (2 * np.pi * frequency)**2)  # [F].
    ec_check = electron_charge**2 / (2 * capacitance * planck_h) / 1e9
    ej_check = (planck_h / (4 * np.pi * electron_charge))**2 / (inductance * planck_h) / 1e9
    if not np.allclose([ec, ej, float(model["C_effective_fF"])],
                       [ec_check, ej_check, capacitance * 1e15], rtol=1e-8, atol=1e-10):
        raise ValueError("Saved energies/capacitance do not match the L/f conversions.")

    def physical_matrix(n):
        # Charging is diagonal; Josephson tunnelling shifts charge by one pair.
        hop = np.full(len(n) - 1, -ej / 2)
        return np.diag(4 * ec * (n - ng)**2) + np.diag(hop, 1) + np.diag(hop, -1)

    matrix = physical_matrix(charge)
    levels = np.linalg.eigvalsh(matrix)
    if padding <= levels[1]:
        raise ValueError("Padding must lie above the first physical excited level.")
    embedded = padding * np.eye(2**qubits)
    embedded[:dimension, :dimension] = matrix
    observable = SparsePauliOp.from_operator(Operator(embedded), atol=1e-12, rtol=0)
    assert np.allclose(observable.to_matrix(), embedded, atol=1e-9, rtol=0)
    larger = np.linalg.eigvalsh(physical_matrix(np.arange(-cutoff - 2, cutoff + 3)))
    reference = {
        "E0_GHz": float(levels[0]), "E1_GHz": float(levels[1]),
        "f01_GHz": float(levels[1] - levels[0]),
        "f01_at_N_plus_2_GHz": float(larger[1] - larger[0]),
        "cutoff_shift_Hz": float((larger[1] - larger[0] - levels[1] + levels[0]) * 1e9),
        "usage": "Validation only; never used to choose angles or optimizer candidates.",
    }
    return reference, observable


# 3.2 Step 2: compile for the target and apply its layout to the observable.
class Compiler:
    def __init__(self, backend, seed: int, level: int, layout: list[int] | None):
        self.backend, self.seed, self.level, self.layout = backend, seed, level, layout

    def run(self, circuit: QuantumCircuit) -> QuantumCircuit:
        pm = generate_preset_pass_manager(
            backend=self.backend, optimization_level=self.level,
            seed_transpiler=self.seed, initial_layout=self.layout,
        )
        compiled = pm.run(circuit)
        if self.layout is None:
            # Reuse the ground circuit's initial physical mapping for the other circuits.
            self.layout = compiled.layout.initial_index_layout(filter_ancillas=True)
        return compiled


def overlap_circuit(excited: WarmState, ground: WarmState, ground_angles: np.ndarray) -> QuantumCircuit:
    """P(0...0) = |<psi_g|psi_e>|^2 for ideal compute-uncompute."""
    circuit = excited.circuit.copy()
    # A barrier also makes the deliberately long self-overlap diagnostic meaningful.
    circuit.barrier()
    circuit.compose(ground.bound(ground_angles).inverse(), inplace=True)
    circuit.measure_all()
    return circuit


def circuit_summary(circuit: QuantumCircuit) -> dict:
    counts = circuit.count_ops()
    two_qubit = sum(len(item.qubits) == 2 and item.operation.name != "barrier" for item in circuit.data)
    return {
        "depth": circuit.depth(), "two_qubit_gates": two_qubit,
        "operations": {name: int(number) for name, number in counts.items()},
        "initial_physical_qubits": circuit.layout.initial_index_layout(filter_ancillas=True),
    }


@dataclass
class Reading:
    energy_GHz: float
    energy_se_GHz: float
    overlap: float = 0.0
    overlap_se: float = 0.0
    overlap_successes: int = 0
    overlap_shots: int = 0

    def cost(self, beta: float) -> float:
        return self.energy_GHz + beta * self.overlap

    def cost_se(self, beta: float) -> float:
        return math.hypot(self.energy_se_GHz, beta * self.overlap_se)


def binomial_summary(successes: int, shots: int) -> tuple[float, float, list[float]]:
    """Return p, a nonzero boundary uncertainty, and a 95% Wilson interval."""
    p = successes / shots
    z = 1.959963984540054
    denominator = 1 + z**2 / shots
    center = (p + z**2 / (2 * shots)) / denominator
    half = z * math.sqrt(p * (1 - p) / shots + z**2 / (4 * shots**2)) / denominator
    # Wilson half-width/z remains nonzero even if no all-zero events are observed.
    return p, half / z, [max(0.0, center - half), min(1.0, center + half)]


# 3.3 Step 3: costs are measured; Adam uses SPSA finite perturbations.
class Measurements:
    def __init__(self, estimator, sampler, report: dict, output: Path, local: bool):
        self.estimator, self.sampler = estimator, sampler
        self.report, self.output, self.local = report, output, local
        self.energy_points = 0
        self.overlap_points = 0
        self.population_points = 0

    def submit(self, primitive, pubs, kind: str, shots: int, label: str):
        if kind == "energy":
            if self.local:
                job = primitive.run(pubs)  # Exact local energy; no artificial Gaussian noise.
            else:
                primitive.options.default_shots = shots
                job = primitive.run(pubs)
        else:
            job = primitive.run(pubs, shots=shots)
        entry = {
            "kind": kind, "label": label, "job_id": str(job.job_id()),
            "nominal_shots_per_configuration": shots,
            "status": "submitted",
        }
        self.report["jobs"].append(entry)
        write_json(self.output, self.report)
        return job, entry

    def finish(self, submitted):
        job, entry = submitted
        result = job.result()
        entry["status"] = "completed"
        write_json(self.output, self.report)
        return result

    def energies(self, specs: list[tuple], shots: int, label: str) -> list[list[Reading]]:
        pubs = [(isa, op, state.values_for(isa, points)) for state, isa, op, points in specs]
        self.energy_points += sum(len(points) for _, _, _, points in specs)
        result = self.finish(self.submit(self.estimator, pubs, "energy", shots, label))
        readings = []
        for pub, (_, _, _, points) in zip(result, specs):
            values = np.asarray(pub.data.evs, dtype=float).ravel()
            errors = np.asarray(pub.data.stds, dtype=float).ravel()
            if len(values) != len(points) or len(errors) != len(points):
                raise RuntimeError("Unexpected Estimator PUB result shape.")
            if not np.all(np.isfinite(values)) or not np.all(np.isfinite(errors)) or np.any(errors < 0):
                raise RuntimeError("Estimator returned invalid energies or uncertainties.")
            readings.append([Reading(float(v), float(s)) for v, s in zip(values, errors)])
        return readings

    def counts(self, state: WarmState, isa: QuantumCircuit, points: np.ndarray,
               shots: int, label: str, kind="overlap") -> list[dict]:
        if kind == "overlap":
            self.overlap_points += len(points)
        else:
            self.population_points += len(points)
        circuit = isa
        if self.local:
            # StatevectorSampler strips measurements internally. A fresh circuit
            # retains all compiled operations/registers without stale layout metadata.
            circuit = QuantumCircuit(*isa.qregs, *isa.cregs)
            circuit.compose(isa, inplace=True)
        pub = (circuit, state.values_for(circuit, points))
        result = self.finish(self.submit(self.sampler, [pub], kind, shots, label))[0]
        return [result.data.meas.get_counts(loc=index) for index in range(len(points))]

    def overlaps(self, state: WarmState, isa: QuantumCircuit, points: np.ndarray,
                 shots: int, label: str) -> list[tuple[int, int]]:
        counts = self.counts(state, isa, points, shots, label)
        return [(c.get("0" * state.circuit.num_qubits, 0), sum(c.values())) for c in counts]


class Objective:
    def __init__(self, state: WarmState, isa: QuantumCircuit, observable: SparsePauliOp,
                 measurements: Measurements, beta: float = 0.0, overlap_isa=None):
        self.state, self.isa, self.observable = state, isa, observable
        self.measurements, self.beta, self.overlap_isa = measurements, beta, overlap_isa

    def evaluate(self, points, shots: int, label: str) -> list[Reading]:
        points = np.atleast_2d(np.asarray(points, dtype=float))
        energy = self.measurements.energies(
            [(self.state, self.isa, self.observable, points)], shots, label
        )[0]
        if self.overlap_isa is not None:
            overlaps = self.measurements.overlaps(self.state, self.overlap_isa, points, shots, label)
            for reading, (successes, total) in zip(energy, overlaps):
                p, se, _ = binomial_summary(successes, total)
                reading.overlap, reading.overlap_se = p, se
                reading.overlap_successes, reading.overlap_shots = successes, total
        return energy


def adam_spsa(objective: Objective, start: np.ndarray, steps: int, args,
              stage: str, history: list) -> list[dict]:
    """Rademacher SPSA gradient estimates fed to bias-corrected Adam updates.

    Two objective values per random direction estimate all gradient components.
    This is not a parameter-shift gradient and uses no full-state information.
    Angles are not wrapped modulo 2*pi: controlled RY has a 4*pi period.
    """
    rng = np.random.default_rng(args.seed + (0 if stage == "ground" else 1000))
    theta = np.array(start, dtype=float, copy=True)
    m, v = np.zeros_like(theta), np.zeros_like(theta)
    candidates = []
    started = perf_counter()

    def keep(point, reading, iteration, kind):
        record = {
            "iteration": iteration, "kind": kind, "parameters_rad": point.tolist(),
            **asdict(reading), "cost_GHz": reading.cost(objective.beta),
            "cost_se_GHz": reading.cost_se(objective.beta),
        }
        candidates.append(record)
        return record

    baseline = objective.evaluate([theta], args.shots, f"{stage}:warm_start")[0]
    initial = keep(theta, baseline, 0, "warm_start")
    history.append(dict(initial, elapsed_seconds=perf_counter() - started))
    print(f"{stage}: warm-start cost = {initial['cost_GHz']:.9f} GHz", flush=True)
    for k in range(1, steps + 1):
        c_k = args.perturbation / k**0.101  # Perturbation scale [rad].
        directions = rng.choice([-1.0, 1.0], size=(args.resamplings, len(theta)))
        points = np.array([point for delta in directions for point in (theta + c_k*delta, theta - c_k*delta)])
        readings = objective.evaluate(points, args.shots, f"{stage}:gradient:{k}")
        costs = np.array([r.cost(objective.beta) for r in readings]).reshape(-1, 2)
        gradient = np.mean(((costs[:, 0] - costs[:, 1]) / (2*c_k))[:, None] * directions, axis=0)
        for point, reading in zip(points, readings):
            keep(point, reading, k, "spsa_probe")
        m = 0.9*m + 0.1*gradient
        v = 0.999*v + 0.001*gradient**2
        m_hat, v_hat = m/(1-0.9**k), v/(1-0.999**k)
        step = (args.learning_rate / k**0.1) * m_hat / (np.sqrt(v_hat) + 1e-8)
        # A modest update cap protects an already accurate classical warm start.
        norm = np.linalg.norm(step)
        if norm > args.max_update_norm:
            step *= args.max_update_norm/norm
        theta -= step
        if k % args.checkpoint_every == 0 or k == steps:
            reading = objective.evaluate([theta], args.shots, f"{stage}:checkpoint:{k}")[0]
            record = keep(theta, reading, k, "checkpoint")
            history.append(dict(record, elapsed_seconds=perf_counter() - started,
                                spsa_gradient_norm=float(np.linalg.norm(gradient))))
            print(f"{stage}: step {k}, cost = {record['cost_GHz']:.9f} GHz", flush=True)
    return candidates


def aggregate(readings: list[Reading], beta: float) -> dict:
    energies = np.array([r.energy_GHz for r in readings])
    within = math.sqrt(sum(r.energy_se_GHz**2 for r in readings))/len(readings)
    between = float(np.std(energies, ddof=1)/np.sqrt(len(readings))) if len(readings) > 1 else 0.0
    successes = sum(r.overlap_successes for r in readings)
    shots = sum(r.overlap_shots for r in readings)
    p, se, interval = binomial_summary(successes, shots) if shots else (0.0, 0.0, [0.0, 0.0])
    energy, energy_se = float(np.mean(energies)), max(within, between)
    return {
        "energy_GHz": energy, "energy_se_GHz": energy_se,
        "raw_compute_uncompute_probability": p if shots else None,
        "overlap_se": se if shots else None,
        "overlap_wilson_95_interval": interval if shots else None, "overlap_shots": shots,
        "cost_GHz": energy + beta*p, "cost_se_GHz": math.hypot(energy_se, beta*se),
    }


def select_remeasured(objective: Objective, candidates: list[dict], args, stage: str) -> dict:
    """Include the warm start and independently remeasure a noisy-cost shortlist."""
    shortlist = [candidates[0]]
    seen = {tuple(candidates[0]["parameters_rad"])}
    for candidate in sorted(candidates, key=lambda c: c["cost_GHz"]):
        key = tuple(candidate["parameters_rad"])
        if key not in seen and len(shortlist) < args.shortlist:
            shortlist.append(candidate)
            seen.add(key)
    points = np.array([c["parameters_rad"] for c in shortlist for _ in range(args.final_repeats)])
    readings = objective.evaluate(points, args.validation_shots, f"{stage}:independent_selection")
    assessed = []
    for index, candidate in enumerate(shortlist):
        subset = readings[index*args.final_repeats:(index+1)*args.final_repeats]
        assessed.append({"parameters_rad": candidate["parameters_rad"],
                         "training_origin": candidate["kind"], **aggregate(subset, objective.beta)})
    baseline = assessed[0]
    eligible = [r for r in assessed[1:] if r["cost_GHz"] < baseline["cost_GHz"]
                - args.selection_sigma*math.hypot(r["cost_se_GHz"], baseline["cost_se_GHz"])]
    selected = min(eligible, key=lambda r: r["cost_GHz"]) if eligible else baseline
    return {"selected": selected, "shortlist": assessed,
            "criterion": "Lowest independently remeasured mean cost with a statistical improvement guard relative to the warm start. This heuristic is not a global optimum or confidence guarantee.",
            "selection_sigma": args.selection_sigma}


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--parameters", type=Path, default=Path("single_transmon_best_parameters.json"))
    parser.add_argument("--mode", choices=("plan", "local", "hardware"), default="plan")
    parser.add_argument("--backend", help="Named IBM backend; otherwise least-busy in hardware mode.")
    parser.add_argument("--account", help="Optional saved IBM account name; credentials stay outside this script.")
    parser.add_argument("--initial-layout", help="Optional comma-separated physical qubits, one per logical qubit.")
    parser.add_argument("--ground-steps", type=int, default=10)
    parser.add_argument("--excited-steps", type=int, default=10)
    parser.add_argument("--shots", type=int, default=4096, help="Training shots per energy configuration / overlap PUB.")
    parser.add_argument("--validation-shots", type=int, default=16384)
    parser.add_argument("--final-repeats", type=int, default=3)
    parser.add_argument("--shortlist", type=int, default=3)
    parser.add_argument("--selection-sigma", type=float, default=2.0,
                        help="Keep warm start unless remeasured cost improves beyond this uncertainty multiplier.")
    parser.add_argument("--learning-rate", type=float, default=0.01, help="Adam step coefficient [rad].")
    parser.add_argument("--perturbation", type=float, default=0.05, help="SPSA perturbation coefficient [rad].")
    parser.add_argument("--resamplings", type=int, default=1, help="Independent SPSA directions per step.")
    parser.add_argument("--max-update-norm", type=float, default=0.05, help="Maximum angle update norm [rad].")
    parser.add_argument("--checkpoint-every", type=int, default=5)
    parser.add_argument("--optimization-level", type=int, choices=(0, 1, 2, 3), default=1)
    parser.add_argument("--resilience-level", type=int, choices=(0, 1, 2), default=1)
    parser.add_argument("--max-job-seconds", type=int, default=300, help="Runtime maximum QPU seconds per job.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("single_transmon_ibm_results.json"))
    parser.add_argument("--plot", action="store_true", help="Display plots; never save separate figure files.")
    args = parser.parse_args(argv)
    positive = ("shots", "validation_shots", "final_repeats", "shortlist", "resamplings", "checkpoint_every", "max_job_seconds")
    for name in positive:
        if getattr(args, name) < 1:
            parser.error(f"--{name.replace('_', '-')} must be positive.")
    for name in ("learning_rate", "perturbation", "max_update_norm"):
        if not np.isfinite(getattr(args, name)) or getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be finite and positive.")
    if not np.isfinite(args.selection_sigma) or args.selection_sigma < 0:
        parser.error("--selection-sigma must be finite and nonnegative.")
    if min(args.ground_steps, args.excited_steps, args.seed) < 0:
        parser.error("Step counts and seed must be nonnegative.")
    if args.mode == "local" and args.backend:
        parser.error("A real --backend belongs to plan or hardware mode, not local mode.")
    if args.parameters.resolve() == args.output.resolve():
        parser.error("The results file must not overwrite the input parameters file.")
    return args


def get_backend(args, qubits: int):
    if args.mode == "hardware" or args.backend:
        from qiskit_ibm_runtime import QiskitRuntimeService
        service = QiskitRuntimeService(name=args.account) if args.account else QiskitRuntimeService()
        backend = service.backend(args.backend) if args.backend else service.least_busy(
            min_num_qubits=qubits, operational=True, simulator=False,
        )
        if backend.num_qubits < qubits or backend.configuration().simulator or not backend.status().operational:
            raise ValueError("Select an operational real processor with enough qubits.")
        return backend
    return GenericBackendV2(
        num_qubits=qubits, basis_gates=["rz", "sx", "x", "cx"],
        coupling_map=CouplingMap.from_line(qubits), seed=args.seed, noise_info=False,
    )


def make_measurements(args, backend, report):
    if args.mode == "local":
        estimator = StatevectorEstimator(default_precision=0.0, seed=args.seed)
        sampler = StatevectorSampler(seed=np.random.default_rng(args.seed), default_shots=args.shots)
    else:
        # Runtime V2 APIs: job mode works without requiring session entitlement.
        from qiskit_ibm_runtime import EstimatorV2 as RuntimeEstimator, SamplerV2 as RuntimeSampler
        estimator = RuntimeEstimator(mode=backend, options={
            "default_shots": args.shots, "resilience_level": args.resilience_level,
            "max_execution_time": args.max_job_seconds,
        })
        sampler = RuntimeSampler(mode=backend, options={
            "default_shots": args.shots, "max_execution_time": args.max_job_seconds,
        })
    return Measurements(estimator, sampler, report, args.output, args.mode == "local")


def plot_results(report: dict) -> None:
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    g, ex = report["ground_history"], report["excited_history"]
    axes[0, 0].errorbar([r["iteration"] for r in g], [r["energy_GHz"] for r in g],
                        yerr=[r["energy_se_GHz"] for r in g], fmt="o-", label="Measured VQE")
    axes[0, 0].axhline(report["exact_reference"]["E0_GHz"], ls="--", color="black", label="Exact charge model")
    axes[0, 0].set(title="Ground-state VQE", xlabel="Adam-SPSA step", ylabel="Energy / h [GHz]")
    axes[0, 1].plot([r["iteration"] for r in ex], [r["cost_GHz"] for r in ex], "o-", label="VQD cost")
    axes[0, 1].plot([r["iteration"] for r in ex], [r["energy_GHz"] for r in ex], "o-", label="Physical energy")
    axes[0, 1].axhline(report["exact_reference"]["E1_GHz"], ls="--", color="black", label="Exact E1")
    axes[0, 1].set(title="First-excited-state VQD", xlabel="Adam-SPSA step", ylabel="Energy / h [GHz]")
    axes[1, 0].plot([r["iteration"] for r in ex], [r["overlap"] for r in ex], "o-")
    axes[1, 0].set(title="Raw compute-uncompute probability", xlabel="Adam-SPSA step", ylabel="P(all zero)")
    transition = report["final"]["transition_GHz"]
    axes[1, 1].bar(["Exact model", "Measured VQE/VQD"], [report["exact_reference"]["f01_GHz"], transition])
    axes[1, 1].errorbar([1], [transition], yerr=[report["final"]["transition_se_GHz"]], fmt="none", color="black", capsize=5)
    axes[1, 1].set(title="Ground-to-first-excited transition", ylabel="f01 [GHz]")
    for ax in axes[0]:
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig2, axes2 = plt.subplots(1, 2, figsize=(11, 4))
    for label in ("ground", "excited"):
        population = report["populations"][label]
        axes2[0].plot(population["physical_charge_values"], population["physical_charge_probabilities"], "o-", label=label)
    axes2[0].set(xlabel="Excess Cooper-pair charge n", ylabel="Measured probability", title="Charge distributions")
    axes2[0].legend()
    axes2[1].bar(["Ground", "Excited"], [report["populations"][label]["padding_probability"] for label in ("ground", "excited")])
    axes2[1].set(ylabel="Measured probability", title="Population in unused padding states")
    fig2.tight_layout()
    plt.show()  # Explicit display only; no savefig call.


def main(argv=None) -> int:
    args = arguments(argv)
    data, ground, excited = load_warm_starts(args.parameters)
    references, observable = build_model(data, ground, excited)
    backend = get_backend(args, ground.circuit.num_qubits)
    layout = [int(x) for x in args.initial_layout.split(",")] if args.initial_layout else None
    if layout is not None and (len(layout) != ground.circuit.num_qubits or len(set(layout)) != len(layout)
                               or min(layout) < 0 or max(layout) >= backend.num_qubits):
        raise ValueError("Initial layout must contain one distinct valid physical qubit per logical qubit.")
    compiler = Compiler(backend, args.seed, args.optimization_level, layout)
    started = perf_counter()
    ground_isa = compiler.run(ground.circuit)
    excited_isa = compiler.run(excited.circuit)
    ground_op = observable.apply_layout(ground_isa.layout)
    excited_op = observable.apply_layout(excited_isa.layout)
    warm_overlap_isa = compiler.run(overlap_circuit(excited, ground, ground.angles))
    compilation_seconds = perf_counter() - started
    report = {
        "schema_version": 1, "status": "planned", "mode": args.mode,
        "created_utc": datetime.now(timezone.utc).isoformat(), "versions": versions(),
        "backend": backend.name, "physical_model": data["model"],
        "classical_warm_start_transition_GHz": data.get("transition_GHz"),
        "exact_reference": references,
        "settings": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        "compilation_seconds": compilation_seconds,
        "compiled": {"ground": circuit_summary(ground_isa), "excited": circuit_summary(excited_isa),
                     "warm_start_overlap": circuit_summary(warm_overlap_isa)},
        "pauli_terms": len(observable), "jobs": [], "ground_history": [], "excited_history": [],
        "scope": {
            "energy_units": "E/h in GHz", "angle_units": "radians",
            "local_mode": "Exact statevector energies and finite-shot ideal overlap samples; not a device-noise simulation.",
            "hardware_mode": "Runtime energy measurements and raw Sampler compute-uncompute probabilities.",
            "uncertainty": "Statistical/repeat estimates assuming independent energy sampling; gate/readout bias and device drift are not fully accounted for. Overlap uncertainty is Wilson half-width/1.96.",
            "shot_budget": "Energy shots are per measurement configuration, not total shots over all Pauli terms or mitigations.",
            "timings": "Wall time includes submission, queue, execution and local processing; not pure QPU time.",
        },
    }
    print(f"Model: {ground.circuit.num_qubits} qubits; {len(observable)} Pauli terms; backend {backend.name}")
    for name, item in report["compiled"].items():
        print(f"{name}: depth {item['depth']}; two-qubit gates {item['two_qubit_gates']}")
    if args.mode == "plan":
        print("Plan complete: no primitive jobs submitted and no results file written.")
        print("The offline generic target is only an estimate unless --backend selected an actual device.")
        return 0

    report["status"] = "running"
    write_json(args.output, report)
    try:
        measurements = make_measurements(args, backend, report)
        start = perf_counter()
        g_objective = Objective(ground, ground_isa, ground_op, measurements)
        candidates = adam_spsa(g_objective, ground.angles, args.ground_steps, args, "ground", report["ground_history"])
        report["ground_selection"] = select_remeasured(g_objective, candidates, args, "ground")
        ground_angles = np.array(report["ground_selection"]["selected"]["parameters_rad"])
        report["ground_parameters"] = ground.export(ground_angles)
        write_json(args.output, report)

        # Freeze the hardware-selected ground circuit, not a simulated statevector.
        overlap_isa = compiler.run(overlap_circuit(excited, ground, ground_angles))
        report["compiled"]["selected_ground_overlap"] = circuit_summary(overlap_isa)
        beta = float(data["model"]["beta_GHz"])
        e_objective = Objective(excited, excited_isa, excited_op, measurements, beta, overlap_isa)
        candidates = adam_spsa(e_objective, excited.angles, args.excited_steps, args, "excited", report["excited_history"])
        report["excited_selection"] = select_remeasured(e_objective, candidates, args, "excited")
        excited_angles = np.array(report["excited_selection"]["selected"]["parameters_rad"])
        report["excited_parameters"] = excited.export(excited_angles)

        # 3.4 Step 4: fresh measurements after selection avoid reporting only a noisy minimum.
        repeats = args.final_repeats
        final_energy = measurements.energies([
            (ground, ground_isa, ground_op, np.tile(ground_angles, (repeats, 1))),
            (excited, excited_isa, excited_op, np.tile(excited_angles, (repeats, 1))),
        ], args.validation_shots, "fresh_final_energies")
        g_final, e_final = (aggregate(values, 0.0) for values in final_energy)
        overlap_counts = measurements.overlaps(excited, overlap_isa,
            np.tile(excited_angles, (repeats, 1)), args.validation_shots, "fresh_final_overlap")
        success, total = sum(x[0] for x in overlap_counts), sum(x[1] for x in overlap_counts)
        p, p_se, interval = binomial_summary(success, total)
        e_final.update({
            "raw_compute_uncompute_probability": p, "overlap_se": p_se,
            "overlap_wilson_95_interval": interval, "overlap_shots": total,
            "cost_GHz": e_final["energy_GHz"] + beta*p,
            "cost_se_GHz": math.hypot(e_final["energy_se_GHz"], beta*p_se),
        })

        # A long identity experiment diagnoses noise in compute-uncompute itself.
        self_isa = compiler.run(overlap_circuit(ground, ground, ground_angles))
        self_counts = measurements.overlaps(ground, self_isa, np.array([ground_angles]),
                                            args.validation_shots, "ground_self_overlap_diagnostic")[0]
        self_p, _, self_interval = binomial_summary(*self_counts)
        report["populations"] = {}
        dimension = int(data["model"]["physical_dimension"])
        cutoff = int(data["model"]["charge_cutoff_N"])
        for label, state, angles in (("ground", ground, ground_angles), ("excited", excited, excited_angles)):
            population_circuit = state.circuit.copy()
            population_circuit.measure_all()
            population_isa = compiler.run(population_circuit)
            counts = measurements.counts(state, population_isa, np.array([angles]),
                args.validation_shots, f"{label}:charge_populations", kind="population")[0]
            shots = sum(counts.values())
            padding_count = sum(count for bits, count in counts.items() if int(bits, 2) >= dimension)
            padding_p, _, padding_interval = binomial_summary(padding_count, shots)
            report["populations"][label] = {
                "counts": counts, "shots": shots, "padding_probability": padding_p,
                "padding_wilson_95_interval": padding_interval,
                "physical_charge_values": list(range(-cutoff, cutoff + 1)),
                "physical_charge_probabilities": [counts.get(format(k, f"0{state.circuit.num_qubits}b"), 0)/shots
                                                   for k in range(dimension)],
                "interpretation": "Raw readout distribution, not renormalized to the physical subspace or corrected for readout errors.",
            }
        transition = e_final["energy_GHz"] - g_final["energy_GHz"]
        transition_se = math.hypot(g_final["energy_se_GHz"], e_final["energy_se_GHz"])
        report["final"] = {
            "ground": g_final, "excited": e_final,
            "transition_GHz": transition, "transition_se_GHz": transition_se,
            "transition_abs_error_kHz": abs(transition - references["f01_GHz"])*1e6,
            "raw_compute_uncompute_probability": p, "overlap_se": p_se,
            "overlap_wilson_95_interval": interval, "overlap_shots": total,
            "ground_self_overlap_probability": self_p, "self_overlap_wilson_95_interval": self_interval,
            "overlap_interpretation": "On a noisy QPU this probability is a diagnostic, not an unbiased true-state fidelity. Self-overlap should ideally equal 1; no ad-hoc normalization is applied.",
            "ground_error_kHz": abs(g_final["energy_GHz"] - references["E0_GHz"])*1e6,
            "excited_error_kHz": abs(e_final["energy_GHz"] - references["E1_GHz"])*1e6,
        }
        report["wall_seconds"] = perf_counter() - start
        report["energy_parameter_points"] = measurements.energy_points
        report["overlap_parameter_points"] = measurements.overlap_points
        report["population_parameter_points"] = measurements.population_points
        report["status"] = "completed"
        write_json(args.output, report)
        print(f"E0/h = {g_final['energy_GHz']:.9f} +/- {g_final['energy_se_GHz']:.3g} GHz (statistical)")
        print(f"E1/h = {e_final['energy_GHz']:.9f} +/- {e_final['energy_se_GHz']:.3g} GHz (statistical)")
        print(f"f01 = {transition:.9f} +/- {transition_se:.3g} GHz (statistical)")
        print(f"Absolute frequency error versus charge model: {report['final']['transition_abs_error_kHz']:.3f} kHz")
        print(f"Raw overlap probability: {p:.5f}; self-overlap diagnostic: {self_p:.5f}")
        print(f"Padding probabilities: ground {report['populations']['ground']['padding_probability']:.5f}, excited {report['populations']['excited']['padding_probability']:.5f}")
        print(f"Results and job IDs: {args.output.resolve()}")
        if args.plot:
            plot_results(report)
        return 0
    except BaseException as exc:
        # Preserve submitted job IDs on failure; never automatically resubmit paid jobs.
        report["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        report["error_type"] = type(exc).__name__
        write_json(args.output, report)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
