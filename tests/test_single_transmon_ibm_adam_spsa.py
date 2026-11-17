"""Offline tests: real Runtime local-testing APIs, no accounts or QPU jobs."""
import base64
from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from qiskit import QuantumCircuit, qpy
from qiskit.circuit import ParameterVector
from qiskit.circuit.library import RYGate
from qiskit.quantum_info import Statevector

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("transmon_ibm", ROOT / "single_transmon_ibm_adam_spsa.py")
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def make_fixture(path):
    """Use the notebook's ansatz with a tiny cutoff to keep API tests fast."""
    inductance, frequency = 10e-9, 5.21015e9
    capacitance = 1 / (inductance * (2*np.pi*frequency)**2)
    ec = m.electron_charge**2 / (2 * capacitance * m.planck_h) / 1e9
    ej = (m.planck_h/(4*np.pi*m.electron_charge))**2 / (inductance*m.planck_h) / 1e9
    physical = np.diag(4*ec*np.array([-1.,0.,1.])**2) + np.diag([-ej/2]*2,1) + np.diag([-ej/2]*2,-1)
    levels, vectors = np.linalg.eigh(physical)
    data = {"schema_version":1, "model":{
        "L_J_nH":10., "f_linear_GHz":5.21015, "C_effective_fF":capacitance*1e15,
        "E_C_over_h_GHz":ec, "E_J_over_h_GHz":ej, "n_g":0.,
        "charge_cutoff_N":1, "num_qubits":2, "physical_dimension":3,
        "padding_energy_GHz":float(levels[1]+10), "beta_GHz":float(2*(levels[1]-levels[0])),
    }}
    for label, index in (("ground",0),("excited",1)):
        reference = 1 if label == "ground" else 0
        targets = [k for k in range(3) if k != reference]
        parameters = ParameterVector("theta_" + label, 2)
        circuit = QuantumCircuit(2)
        for target, parameter in zip(targets, parameters):
            bits = [k for k in range(2) if (reference ^ target) & (1<<k)]
            pivot, *tail = bits
            for bit in tail:
                circuit.cx(pivot,bit)
            circuit.append(RYGate(parameter).control(1,ctrl_state=0), [1-pivot,pivot])
            for bit in reversed(tail):
                circuit.cx(pivot,bit)
        if reference:
            circuit.x(0)
        vector = vectors[:,index].copy()
        if vector[reference] < 0:
            vector *= -1
        angles = [2*np.arctan2(vector[target], np.sqrt(vector[reference]**2 + np.sum(vector[targets[k+1:]]**2)))
                  for k,target in enumerate(targets)]
        buffer = io.BytesIO()
        qpy.dump(circuit,buffer)
        # Deliberately reverse the saved order: name mapping must fix this.
        data[label] = {"parameter_order":[p.name for p in circuit.parameters][::-1],
                       "parameters_rad":angles[::-1],
                       "logical_circuit_qpy_base64":base64.b64encode(buffer.getvalue()).decode()}
    path.write_text(json.dumps(data))
    return data


class HardwareScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.parameters = self.folder / "warm.json"
        self.data = make_fixture(self.parameters)

    def test_parameter_order_and_model_conversion(self):
        data, ground, excited = m.load_warm_starts(self.parameters)
        reference, observable = m.build_model(data,ground,excited)
        for state, energy in ((ground,reference["E0_GHz"]),(excited,reference["E1_GHz"])):
            vector = Statevector.from_instruction(state.bound(state.angles).decompose()).data
            self.assertAlmostEqual(float(np.vdot(vector,observable.to_matrix() @ vector).real),energy,places=10)
        self.assertLess(reference["E0_GHz"],reference["E1_GHz"])
        bad = deepcopy(data)
        bad["model"]["E_C_over_h_GHz"] *= 2
        with self.assertRaisesRegex(ValueError,"conversions"):
            m.build_model(bad,ground,excited)

    def test_plan_submits_nothing(self):
        output = self.folder / "plan.json"
        with patch.object(m,"make_measurements",side_effect=AssertionError("Must not submit")), redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(["--parameters",str(self.parameters),"--output",str(output)]),0)
        self.assertFalse(output.exists())

    def test_adam_spsa_estimates_gradients(self):
        class Quadratic:
            beta = 0.0
            def evaluate(self,points,shots,label):
                return [m.Reading(float((np.asarray(p)[0]-.2)**2),0.) for p in points]
        args = SimpleNamespace(seed=42,shots=1,resamplings=1,perturbation=.05,
                               learning_rate=.08,max_update_norm=.1,checkpoint_every=10)
        with redirect_stdout(io.StringIO()):
            candidates = m.adam_spsa(Quadratic(),np.array([1.]),40,args,"ground",[])
        self.assertLess(min(c["cost_GHz"] for c in candidates),1e-3)

    def test_vqd_selection_uses_penalty(self):
        class MeasuredVQD:
            beta = 20.
            def evaluate(self,points,shots,label):
                return [m.Reading(-10.,0.,1.,0.,shots,shots) if p[0] == 0
                        else m.Reading(-5.,0.,0.,0.,0,shots) for p in points]
        candidates = [{"parameters_rad":[0.],"cost_GHz":-100.,"kind":"warm_start"},
                      {"parameters_rad":[1.],"cost_GHz":-1.,"kind":"checkpoint"}]
        result = m.select_remeasured(MeasuredVQD(),candidates,
                                    SimpleNamespace(shortlist=2,final_repeats=2,validation_shots=128,selection_sigma=2.),"excited")
        self.assertEqual(result["selected"]["parameters_rad"],[1.])

    def test_full_local_pipeline_and_result_circuits(self):
        output = self.folder / "local.json"
        with redirect_stdout(io.StringIO()):
            status = m.main(["--parameters",str(self.parameters),"--mode","local",
                "--ground-steps","2","--excited-steps","2","--shots","64",
                "--validation-shots","128","--final-repeats","2","--shortlist","2",
                "--checkpoint-every","1","--output",str(output)])
        report = json.loads(output.read_text())
        self.assertEqual(status,0)
        self.assertEqual(report["status"],"completed")
        self.assertAlmostEqual(report["final"]["transition_GHz"],report["exact_reference"]["f01_GHz"],places=9)
        self.assertEqual(report["final"]["ground_self_overlap_probability"],1.)
        self.assertEqual(report["final"]["raw_compute_uncompute_probability"],0.)
        self.assertEqual(report["populations"]["ground"]["padding_probability"],0.)
        self.assertEqual(report["populations"]["excited"]["padding_probability"],0.)
        self.assertTrue(all(job["status"] == "completed" for job in report["jobs"]))
        self.assertGreater(report["energy_parameter_points"],0)
        for key in ("ground_parameters","excited_parameters"):
            circuit = qpy.load(io.BytesIO(base64.b64decode(report[key]["logical_circuit_qpy_base64"])))[0]
            self.assertEqual(circuit.num_parameters,2)

    def test_real_runtime_v2_local_testing_mode(self):
        # Real installed Runtime classes execute on a GenericBackendV2 locally.
        # No service object, account, or network connection is constructed.
        output = self.folder / "runtime_local.json"
        fake_args = SimpleNamespace(mode="local",backend=None,seed=42)
        backend = m.get_backend(fake_args,2)
        with patch.object(m,"get_backend",return_value=backend), redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(["--parameters",str(self.parameters),"--mode","hardware",
                "--ground-steps","0","--excited-steps","0","--shots","64",
                "--validation-shots","64","--final-repeats","1","--shortlist","1",
                "--resilience-level","0","--output",str(output)]),0)
        report = json.loads(output.read_text())
        self.assertEqual(report["status"],"completed")
        self.assertTrue(np.isfinite(report["final"]["transition_GHz"]))
        self.assertTrue(any(job["kind"] == "overlap" for job in report["jobs"]))
        self.assertGreaterEqual(report["final"]["transition_se_GHz"],0.)

    def test_binomial_boundary_uncertainty(self):
        p,se,interval = m.binomial_summary(0,100)
        self.assertEqual(p,0.)
        self.assertGreater(se,0.)
        self.assertGreater(interval[1],0.)


if __name__ == "__main__":
    unittest.main(verbosity=2)
