"""Check repository packaging without executing notebooks or contacting IBM."""
import ast
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
PRIMARY_NOTEBOOKS=(
    'VQE_VQD_Single_Transmon_Simulation.ipynb',
    'VQE_VQD_Four_Transmons_Final.ipynb',
    'VQE_VQD_Four_Transmons_IBM_ADAM_SPSA.ipynb',
)


def validate():
    errors=[]
    for path in ROOT.rglob('*.ipynb'):
        if any(p in ('.git','.venv','venv','.ipynb_checkpoints') for p in path.parts):continue
        try:
            notebook=json.loads(path.read_text(encoding='utf-8'))
            if notebook.get('nbformat')!=4:errors.append(f'Unsupported notebook format: {path.relative_to(ROOT)}')
            if path.name in PRIMARY_NOTEBOOKS and path.parent==ROOT:
                ids=[c.get('id') for c in notebook['cells'] if c.get('id')]
                if len(ids)!=len(set(ids)):errors.append(f'Duplicate cell IDs: {path.name}')
                for i,cell in enumerate(notebook['cells']):
                    if cell['cell_type']!='code':continue
                    try:ast.parse(''.join(cell['source']))
                    except SyntaxError as exc:errors.append(f'{path.name} cell {i}: {exc.msg}')
                    if any(o.get('output_type')=='error' for o in cell.get('outputs',[])):
                        errors.append(f'Saved error output in primary notebook {path.name} cell {i}')
        except Exception as exc:errors.append(f'{path.relative_to(ROOT)}: {type(exc).__name__}')

    for path in ROOT.rglob('*.md'):
        if any(p in ('.git','.venv','venv') for p in path.parts):continue
        text=path.read_text(encoding='utf-8')
        if sum(line.strip().startswith('```') for line in text.splitlines())%2:
            errors.append(f'Unclosed code fence: {path.relative_to(ROOT)}')
        for href in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
            if href.startswith(('https://','http://','mailto:','#')):continue
            target=unquote(href.split('#',1)[0]).strip('<>')
            if target and not (path.parent/target).exists():
                errors.append(f'Broken local link in {path.relative_to(ROOT)}: {href}')

    manifest=json.loads((ROOT/'docs/consolidation_manifest.json').read_text())
    for entry in manifest['preserved_notebooks']:
        path=ROOT/entry['current_path']
        if not path.exists():
            errors.append(f'Missing preserved notebook: {entry["current_path"]}');continue
        content=path.read_bytes()
        blob=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
        if blob!=entry['original_blob']:errors.append(f'Original notebook changed: {entry["current_path"]}')
    promoted=manifest['new_primary_four_transmon_model']
    if hashlib.sha256((ROOT/promoted['path']).read_bytes()).hexdigest()!=promoted['sha256']:
        errors.append('Promoted four-transmon notebook differs from its consolidation snapshot.')
    payload=json.loads((ROOT/'four_transmon_best_parameters.json').read_text())
    if abs(payload['transition_GHz']-promoted['transition_GHz'])>1e-10:
        errors.append('Four-transmon warm-start payload and promoted model differ.')
    if payload['model']['charge_cutoff_N']!=9 or payload['model']['num_qubits']!=8:
        errors.append('Unexpected current four-transmon model dimensions.')
    if errors:raise AssertionError('\n'.join(errors))
    return {'notebook_versions_preserved':len(manifest['preserved_notebooks']),
            'development_branches':len(manifest['merged_branch_tips']),
            'primary_notebooks':len(PRIMARY_NOTEBOOKS)}


if __name__=='__main__':
    print('Repository checks passed:',validate())
