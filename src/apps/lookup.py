from typing import Dict, Tuple, Optional
from rapidfuzz import process, fuzz

def best_match(query: str, index: Dict[str, str], *, min_score: int = 60) -> Optional[Tuple[str, str, int]]:
    if not index or not query:
        return None
    m = process.extractOne(query, index.keys(), scorer=fuzz.token_set_ratio)
    if not m:
        return None
    key, score, _ = m
    if score < min_score:
        return None
    return key, index[key], int(score)
