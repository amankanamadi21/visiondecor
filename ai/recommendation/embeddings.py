"""
Local embedding model wrapper (decision D006a): sentence-transformers/
all-MiniLM-L6-v2, CPU, 384-dim, no training — chosen over a hosted embedding
API for offline reproducibility (see PLAN.md decision log).

The model is loaded once per process (module-level singleton) since loading
takes real time; both the seed script and the request-time retrieval path
share this loader.

HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE are forced on below, once the model is
already cached locally (~/.cache/huggingface — populated by the first-ever
run, which does need network access to download it). Without this,
`SentenceTransformer(...)` contacts huggingface.co on every load to check
for updates; on a degraded or flaky connection that check can itself hang
for a very long time (observed once during development: a ~61-minute stall
with the local model file already present and never actually needed). Since
D001/D006a's whole point is that this component runs fully offline, it
should never depend on network reachability at all once cached.
"""
from __future__ import annotations

import os

import numpy as np

EMBEDDING_DIM = 384
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model = None


def get_model():
    global _model
    if _model is None:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    """Returns an (n, 384) float32 array, L2-normalized so a plain dot
    product between two rows equals their cosine similarity."""
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(embeddings, dtype=np.float32)


def embed_text(text: str) -> np.ndarray:
    return embed_texts([text])[0]
