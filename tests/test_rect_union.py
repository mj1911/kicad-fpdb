from collections import Counter

from kicad_fpdb.rect_union import union_outline


def _assert_closed_rectilinear_loop(segments):
    for (sx, sy), (ex, ey) in segments:
        assert sx == ex or sy == ey
    counts = Counter(pt for seg in segments for pt in seg)
    assert all(count == 2 for count in counts.values())


def test_union_outline_two_rect_cross_matches_soic_topology():
    # Real SOIC-8 courtyard: union of the true-body rect and the full pad
    # bbox, both already margin-expanded (see design spec).
    body = (-2.2, -2.7, 2.2, 2.7)
    pad_bbox = (-3.7, -2.455, 3.7, 2.455)
    segments = union_outline([body, pad_bbox])

    assert len(segments) == 12
    _assert_closed_rectilinear_loop(segments)

    endpoints = {pt for seg in segments for pt in seg}
    assert (-2.2, -2.7) in endpoints
    assert (2.2, 2.7) in endpoints
    assert (-3.7, -2.455) in endpoints
    assert (3.7, 2.455) in endpoints
    assert (-2.2, -2.455) in endpoints
    assert (2.2, 2.455) in endpoints


def test_union_outline_five_rect_matches_qfp_topology():
    # Real LQFP-32 courtyard: union of the true-body square and one
    # margin-expanded pad-group rect per side (see design spec).
    body = (-3.75, -3.75, 3.75, 3.75)
    left = (-5.175, -3.3, -3.175, 3.3)
    right = (3.175, -3.3, 5.175, 3.3)
    bottom = (-3.3, 3.175, 3.3, 5.175)
    top = (-3.3, -5.175, 3.3, -3.175)
    segments = union_outline([body, left, right, bottom, top])

    assert len(segments) == 20
    _assert_closed_rectilinear_loop(segments)

    endpoints = {pt for seg in segments for pt in seg}
    for corner in [(-3.75, -3.75), (3.75, 3.75), (-3.75, 3.75), (3.75, -3.75)]:
        assert corner in endpoints
    assert (-5.175, -3.3) in endpoints
    assert (5.175, 3.3) in endpoints
    assert (-3.3, -5.175) in endpoints
    assert (3.3, 5.175) in endpoints
