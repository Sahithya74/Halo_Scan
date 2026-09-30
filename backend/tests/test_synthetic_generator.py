import numpy as np

from datasets.synthetic_generator import CLASS_PARAM_RANGES, MIXTURE_RATIO_HALO_THRESHOLD, render_sample


def test_render_sample_produces_valid_image():
    rng = np.random.default_rng(0)
    image, params = render_sample(rng, "csf_like")
    assert image.shape == (512, 512, 3)
    assert image.dtype == np.uint8


def test_invalid_class_never_has_halo():
    rng = np.random.default_rng(1)
    for _ in range(10):
        _, params = render_sample(rng, "invalid")
        assert params["mixture_ratio"] < MIXTURE_RATIO_HALO_THRESHOLD
        assert params["halo_present"] is False


def test_csf_and_saline_ranges_overlap():
    csf = CLASS_PARAM_RANGES["csf_like"]
    saline = CLASS_PARAM_RANGES["saline_like"]
    for key in ("ring_width_ratio", "spread_radius"):
        c_lo, c_hi = csf[key]
        s_lo, s_hi = saline[key]
        overlap = min(c_hi, s_hi) - max(c_lo, s_lo)
        assert overlap > 0, f"{key} ranges should overlap between csf_like and saline_like"


def test_saliva_is_more_distinct_from_csf():
    csf = CLASS_PARAM_RANGES["csf_like"]
    saliva = CLASS_PARAM_RANGES["saliva_like"]
    c_lo, c_hi = csf["spread_radius"]
    sv_lo, sv_hi = saliva["spread_radius"]
    csf_overlap = min(c_hi, sv_hi) - max(c_lo, sv_lo)
    saline = CLASS_PARAM_RANGES["saline_like"]
    s_lo, s_hi = saline["spread_radius"]
    csf_saline_overlap = min(c_hi, s_hi) - max(c_lo, s_lo)
    assert csf_overlap < csf_saline_overlap
