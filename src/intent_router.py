# src/intent_router.py
import os
import re
from typing import Callable, Dict, List, Tuple, Optional
import numpy as np

# Try to import SentenceTransformer, but do not require it.
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:
    SentenceTransformer = None  # type: ignore

# small compiled regex for tokenization (alphanumeric tokens)
_TOKEN_RE = re.compile(r"\b[a-z0-9]+\b", re.I)


class IntentRouter:
    """
    Offline-first intent router.

    Behavior:
      - If EMBED_MODEL_PATH points to a local SentenceTransformer folder and
        TORQUE_FORCE_KEYWORDS != "1", use local embeddings (offline).
      - Otherwise use keyword/anchor fallback (no network).
    """

    def __init__(self, threshold: float = 0.52):
        # embeddings threshold (used only when embeddings loaded)
        self.threshold = float(os.getenv("INTENT_EMBED_THRESHOLD", str(threshold)))
        # minimal token-overlap score for keyword route (configurable)
        self.keyword_min_score = float(os.getenv("INTENT_KEYWORD_MIN_SCORE", "0.15"))

        self.examples: Dict[str, List[str]] = {}
        self.handlers: Dict[str, Callable[[str], str]] = {}
        self._anchors: Dict[str, List[str]] = {}

        self._labels: List[str] = []
        self._example_matrix = None
        self.model = None
        self._use_embeddings = False

        force_keywords = os.getenv("TORQUE_FORCE_KEYWORDS", "") == "1"
        local_path = os.getenv("EMBED_MODEL_PATH", "").strip()

        if (not force_keywords
            and SentenceTransformer is not None
            and local_path
            and os.path.isdir(local_path)):
            try:
                # Force offline behavior for safety
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
                os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
                self.model = SentenceTransformer(local_path)
                self._use_embeddings = True
                print(f"[Router] Using LOCAL embeddings from: {local_path}")
            except Exception as e:
                print(f"[Router] Failed to load local embeddings: {e}. Falling back to keywords.")
        else:
            reason = "forced" if force_keywords else "no local embedding model"
            print(f"[Router] Keyword fallback ({reason}). No internet calls.")

    # -------- public config --------
    def add_intent(
        self,
        name: str,
        examples: List[str],
        handler: Callable[[str], str],
        *,
        anchors: Optional[List[str]] = None,
    ):
        """Register an intent.

        anchors: optional list of substrings (lowercased). If provided, a keyword
        match requires at least one anchor to appear in the user text.
        """
        self.examples[name] = examples or []
        self.handlers[name] = handler
        self._anchors[name] = [a.lower() for a in (anchors or [])]

    def build(self):
        """Precompute embeddings matrix if using SentenceTransformer."""
        if not self._use_embeddings:
            return

        pairs = []
        for label, exs in self.examples.items():
            for ex in exs:
                pairs.append((label, ex))

        if not pairs:
            print("[Router] No example texts found for embedding mode — falling back to keywords.")
            self._use_embeddings = False
            self.model = None
            return

        self._labels = [p[0] for p in pairs]
        texts = [p[1] for p in pairs]
        try:
            self._example_matrix = self.model.encode(texts, normalize_embeddings=True)
        except Exception as e:
            print(f"[Router] Embedding encoding failed: {e}. Falling back to keywords.")
            self._use_embeddings = False
            self.model = None
            self._example_matrix = None

    # ---------- tokenization ----------
    @staticmethod
    def _tok(s: str) -> List[str]:
        if not s:
            return []
        return [t.lower() for t in _TOKEN_RE.findall(s)]

    # ---------- keyword fallback ----------
    def _route_keywords(self, user_text: str) -> Tuple[Optional[str], float]:
        tl = (user_text or "").lower().strip()
        if not tl:
            return None, 0.0

        u = set(self._tok(tl))
        best_label, best_score = None, 0.0

        for label, exs in self.examples.items():
            # If anchors defined, require at least one
            anchors = self._anchors.get(label, [])
            if anchors and not any(a in tl for a in anchors):
                continue

            score = 0.0
            for ex in exs:
                e = set(self._tok(ex))
                if not e:
                    continue
                inter = len(u & e)
                # jaccard-like score
                s = inter / (len(u | e) + 1e-9)
                if s > score:
                    score = s

            if score > best_score:
                best_score = score
                best_label = label

        return (best_label, best_score) if best_score >= self.keyword_min_score else (None, best_score)

    # ---------- embeddings route ----------
    def _route_embeddings(self, user_text: str) -> Tuple[Optional[str], float]:
        if not self.model or self._example_matrix is None or not len(self._example_matrix):
            return None, 0.0
        try:
            uvec = self.model.encode([user_text], normalize_embeddings=True)[0]
            sims = np.dot(self._example_matrix, uvec)
            idx = int(np.argmax(sims))
            best_score = float(sims[idx])
            best_label = self._labels[idx]
            if best_score < self.threshold:
                return None, best_score
            return best_label, best_score
        except Exception as e:
            print(f"[Router] Embedding routing failed: {e}")
            return None, 0.0

    # ---------- public API ----------
    def route(self, user_text: str) -> Tuple[Optional[str], float]:
        if self._use_embeddings and self._example_matrix is not None:
            return self._route_embeddings(user_text)
        return self._route_keywords(user_text)

    def handle(self, user_text: str) -> str:
        import time
        start = time.time()
        label, score = self.route(user_text)
        end = time.time()
        print("[MEASURE] Router latency:", end - start)
        """Run the handler safely, returning a default message on failures."""
        label, score = self.route(user_text)
        if label is None:
            return "I'm not sure what you mean. (Enable a local embedding model to improve routing.)"
        fn = self.handlers.get(label)
        if fn is None:
            return f"(Router) No handler registered for intent '{label}'."
        try:
            return fn(user_text)
        except Exception as e:
            print(f"[Router] Handler '{label}' raised exception: {e}")
            return "Something went wrong handling that request."
