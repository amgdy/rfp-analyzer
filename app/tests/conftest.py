"""Pytest configuration and shared fixtures for RFP Analyzer tests."""

import sys
import types
from pathlib import Path

# Ensure the app directory is on the Python path so that imports like
# ``from services.utils import ...`` work the same way they do when
# Streamlit runs ``main.py`` from the ``app/`` directory.
APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


# ---------------------------------------------------------------------------
# Stub out heavy Azure / agent-framework dependencies that are not available
# in the CI test environment (they require Python 3.13+ and Azure credentials).
# The stubs are only added if the real modules are not already installed.
# ---------------------------------------------------------------------------

_MODULES_TO_STUB = [
    # agent framework
    "agent_framework",
    "agent_framework.azure",
    "agent_framework.openai",
    # azure identity / core
    "azure",
    "azure.identity",
    "azure.core",
    "azure.core.credentials",
    # document intelligence
    "azure.ai",
    "azure.ai.documentintelligence",
    "azure.ai.documentintelligence.models",
    # storage
    "azure.storage",
    "azure.storage.blob",
    "azure.storage.blob.aio",
    # monitor / opentelemetry (used by logging_config in some paths)
    "azure.monitor",
    "azure.monitor.opentelemetry",
    "azure.monitor.opentelemetry.exporter",
]


def _ensure_stub(name: str) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    # Make sure parent is set so submodule resolution works
    parts = name.rsplit(".", 1)
    if len(parts) == 2:
        parent = _ensure_stub(parts[0])
        setattr(parent, parts[1], mod)
    return mod


for _name in _MODULES_TO_STUB:
    _ensure_stub(_name)


# --- Fake classes required by the source modules ---

# agent_framework (top-level)
sys.modules["agent_framework"].Agent = type("Agent", (), {})

# agent_framework.azure
sys.modules["agent_framework.azure"].AzureOpenAIResponsesClient = type(
    "AzureOpenAIResponsesClient", (), {}
)

# agent_framework.openai
sys.modules["agent_framework.openai"].OpenAIChatClient = type(
    "OpenAIChatClient", (), {}
)
sys.modules["agent_framework.openai"].OpenAIChatCompletionClient = type(
    "OpenAIChatCompletionClient", (), {}
)

# azure.identity
sys.modules["azure.identity"].DefaultAzureCredential = type(
    "DefaultAzureCredential", (), {}
)

# azure.core.credentials
sys.modules["azure.core.credentials"].AzureKeyCredential = type(
    "AzureKeyCredential", (), {"__init__": lambda self, key: None}
)

# azure.ai.documentintelligence
_di = sys.modules["azure.ai.documentintelligence"]
_di.DocumentIntelligenceClient = type(
    "DocumentIntelligenceClient", (), {"__init__": lambda self, **kw: None}
)

# azure.ai.documentintelligence.models
_di_models = sys.modules["azure.ai.documentintelligence.models"]
for _cls_name in [
    "AnalyzeDocumentRequest",
    "DocumentContentFormat",
    "AnalyzeResult",
    "AnalyzeOutputOption",
]:
    setattr(_di_models, _cls_name, type(_cls_name, (), {}))

# azure.storage.blob
_blob = sys.modules["azure.storage.blob"]
for _attr in ["BlobServiceClient", "generate_container_sas", "ContainerSasPermissions"]:
    setattr(_blob, _attr, type(_attr, (), {}))

# azure.storage.blob.aio
sys.modules["azure.storage.blob.aio"].ContainerClient = type("ContainerClient", (), {})
