"""Offline packaging and four-transmon plan checks; no QPU jobs or credentials."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import sys
import types
import unittest

import validate_repository

ROOT=Path(__file__).resolve().parents[1]


class RepositoryTests(unittest.TestCase):
    def test_structure_links_and_original_notebooks(self):
        checked=validate_repository.validate()
        self.assertEqual(checked['notebook_versions_preserved'],16)
        self.assertEqual(checked['development_branches'],5)

    def test_four_transmon_default_plan_never_connects(self):
        notebook=json.loads((ROOT/'VQE_VQD_Four_Transmons_IBM_ADAM_SPSA.ipynb').read_text())
        module=types.ModuleType('four_transmon_repository_plan_test')
        sys.modules[module.__name__]=module
        namespace=module.__dict__
        previous=Path.cwd()
        calls=[]
        def forbidden(*args,**kwargs):
            calls.append(True)
            raise AssertionError('Default plan must not connect or submit jobs.')
        try:
            os.chdir(ROOT)
            with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                for cell in notebook['cells']:
                    if cell['cell_type']!='code':continue
                    exec(compile(''.join(cell['source']),'four-transmon-plan','exec'),namespace)
                    # Imports are allowed; construction of account/primitives is not.
                    namespace['QiskitRuntimeService']=forbidden
                    namespace['RuntimeEstimator']=forbidden
                    namespace['RuntimeSampler']=forbidden
            self.assertEqual(namespace['config'].mode,'plan')
            self.assertEqual(namespace['report']['jobs'],[])
            self.assertEqual(len(namespace['ground'].angles),255)
            self.assertEqual(len(namespace['excited'].angles),255)
            self.assertEqual(namespace['hamiltonian'].num_qubits,8)
            self.assertEqual(calls,[])
        finally:
            os.chdir(previous)
            sys.modules.pop(module.__name__,None)


if __name__=='__main__':unittest.main()
