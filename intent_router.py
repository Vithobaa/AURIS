# src/intent_router.py
import os
from typing import Callable, Dict, List, Tuple, Optional
import numpy as np

# Try to import SentenceTransformer, but do not require it.
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:
    SentenceTransformer = None  # type: ignore


class IntentRouter:
    """
    Offline-safe router:
      - If EMBED_MODEL_PATH points to a local folder, use that embedding model.
      - Otherwise, use keyword fallback with *anchors* (no network).
    """
    def __init__(self, threshold: float = 0.52):
        self.threshold = threshold
        self.examples: Dict[str, List[str]] = {}
        self.handlers: Dict[str, Callable[[str], str]] = {}

        self._labels: List[str] = []
        self._example_matrix = None
        self.model = None
        self._use_embeddings = False

        # NEW: intent → list of anchor substrings (lowercased)
        self._anchors: Dict[str, List[str]] = {}

        force_keywords = os.getenv("TORQUE_FORCE_KEYWORDS", "") == "1"
        local_path = os.getenv("EMBED_MODEL_PATH", "").strip()

        if (not force_keywords
            and SentenceTransformer is not None
            and local_path
            and os.path.isdir(local_path)):
            try:
                # Force offline behavior
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
        anchors: Optional[List[str]] = None,   # NEW
    ):
        self.examples[name] = examples or []
        self.handlers[name] = handler
        self._anchors[name] = [a.lower() for a in (anchors or [])]

    def build(self):
        if self._use_embeddings:
            pairs: List[Tuple[str, str]] = []
            for label, exs in self.examples.items():
                for ex in exs:
                    pairs.append((label, ex))
            self._labels = [p[0] for p in pairs]
            texts = [p[1] for p in pairs]
            self._example_matrix = self.model.encode(texts, normalize_embeddings=True)

    # ---------- keyword fallback ----------
    @staticmethod
    def _tok(s: str) -> List[str]:
        return [t for t in ''.join(ch if ch.isalnum() else ' ' for ch in s.lower()).split() if t]

    def _route_keywords(self, user_text: str) -> Tuple[Optional[str], float]:
        tl = (user_text or "").lower().strip()
        if not tl:
            return None, 0.0

        # crude token set for overlap score
        u = set(self._tok(tl))
        best_label, best_score = None, 0.0

        for label, exs in self.examples.items():
            # If intent defines anchors, require at least one to be present
            anchors = self._anchors.get(label, [])
            if anchors:
                if not any(a in tl for a in anchors):
                    continue

            # token overlap vs examples (max over examples)
            score = 0.0
            for ex in exs:
                e = set(self._tok(ex))
                if not e:
                    continue
                inter = len(u & e)
                # Jaccard-ish signal
                s = inter / (len(u | e) + 1e-6)
                if s > score:
                    score = s

            if score > best_score:
                best_score = score
                best_label = label

        # require a minimal match to avoid random triggers
        return (best_label, best_score) if best_score >= 0.15 else (None, best_score)

    # ---------- embeddings route ----------
    def _route_embeddings(self, user_text: str) -> Tuple[Optional[str], float]:
        uvec = self.model.encode([user_text], normalize_embeddings=True)[0]
        sims = np.dot(self._example_matrix, uvec)
        idx = int(np.argmax(sims))
        best_score = float(sims[idx])
        best_label = self._labels[idx]
        if best_score < self.threshold:
            return None, best_score
        return best_label, best_score

    # ---------- public API ----------
    def route(self, user_text: str) -> Tuple[Optional[str], float]:
        if self._use_embeddings and self._example_matrix is not None:
            return self._route_embeddings(user_text)
        return self._route_keywords(user_text)

    def handle(self, user_text: str) -> str:
        label, _ = self.route(user_text)
        if label is None:
            return "I'm not sure what you mean. (Enable online mode later for web answers.)"
        return self.handlers[label](user_text)
