"""Fluid families: the level at which a halo photo can actually be classified reliably.

CSF, saline and tears form optically near-identical halos (clear, low-protein, low-viscosity
fluids), so no image method can reliably tell them apart — the exact-fluid accuracy is
capped by that physics, not by the model. Which *family* a sample belongs to is separable,
and "clear fluid — CSF possible" vs "mucus-rich" vs "other" is the clinically useful
question. Family probabilities are the sums of the calibrated per-class probabilities, so
both levels always come from the same model and can never contradict each other.
"""
from __future__ import annotations

FAMILIES: dict[str, tuple[str, ...]] = {
    "clear_fluid": ("csf_like", "saline_like", "tear_like"),
    "mucus_rich": ("saliva_like", "nasal_mucus_like"),
    "other": ("other",),
}
FAMILY_LABELS = {
    "clear_fluid": "Clear fluid — CSF possible",
    "mucus_rich": "Mucus-rich fluid",
    "other": "Other / atypical",
}
_CLASS_TO_FAMILY = {cls: fam for fam, members in FAMILIES.items() for cls in members}

# Below this family confidence the headline result is reported as UNCERTAIN.
FAMILY_MIN_CONFIDENCE = 0.70


def family_of(cls: str | None) -> str | None:
    return _CLASS_TO_FAMILY.get(cls) if cls else None


def family_probabilities(class_probabilities: dict[str, float]) -> dict[str, float]:
    probs = {fam: 0.0 for fam in FAMILIES}
    for cls, p in class_probabilities.items():
        fam = _CLASS_TO_FAMILY.get(cls)
        if fam:
            probs[fam] += float(p)
    return probs


def family_index_map(classes: list[str]) -> tuple[list[str], list[int]]:
    """(family names, family index for each class index) for vectorised evaluation."""
    names = list(FAMILIES)
    return names, [names.index(_CLASS_TO_FAMILY[c]) for c in classes]
