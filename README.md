# VQE-VQD_for_superconducting_circuits


## Installation & Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd <repository-name>
```

### 2. Create the Python environment

Make sure `pyenv` and `pyenv-virtualenv` are installed.

```bash
pyenv install 3.11
pyenv virtualenv 3.11 qiskit-vqe
pyenv local qiskit-vqe
```

### 3. Activate the environment

```bash
pyenv activate qiskit-vqe
```

### 4. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. Deactivate the environment

```bash
pyenv deactivate
