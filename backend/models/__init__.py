# CompliAI Data Models (Pydantic v2)
# Re-export all models from the parent models.py file
# This package exists for future modular organization

import importlib.util
import os

# Load models.py directly since the package directory shadows it
_models_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models.py')
_spec = importlib.util.spec_from_file_location("_models_file", _models_file)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export everything from models.py
for _name in dir(_mod):
    if not _name.startswith('_'):
        globals()[_name] = getattr(_mod, _name)
