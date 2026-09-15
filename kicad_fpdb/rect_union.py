def union_outline(
    rects: list[tuple[float, float, float, float]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Boundary of the union of axis-aligned rects (each as
    (min_x, min_y, max_x, max_y)), as an ordered closed loop of
    (start, end) segments. Assumes the union is simply connected (no
    holes) -- true for every shape this project constructs."""
    xs = sorted({x for r in rects for x in (r[0], r[2])})
    ys = sorted({y for r in rects for y in (r[1], r[3])})

    def filled(ci: int, cj: int) -> bool:
        if ci < 0 or cj < 0 or ci >= len(xs) - 1 or cj >= len(ys) - 1:
            return False
        cx = (xs[ci] + xs[ci + 1]) / 2
        cy = (ys[cj] + ys[cj + 1]) / 2
        return any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in rects)

    raw_edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for ci in range(len(xs) - 1):
        for cj in range(len(ys) - 1):
            if not filled(ci, cj):
                continue
            x0, x1 = xs[ci], xs[ci + 1]
            y0, y1 = ys[cj], ys[cj + 1]
            if not filled(ci, cj - 1):
                raw_edges.append(((x0, y0), (x1, y0)))
            if not filled(ci, cj + 1):
                raw_edges.append(((x1, y1), (x0, y1)))
            if not filled(ci - 1, cj):
                raw_edges.append(((x0, y1), (x0, y0)))
            if not filled(ci + 1, cj):
                raw_edges.append(((x1, y0), (x1, y1)))

    # Walk the boundary edges into one ordered loop, merging consecutive
    # collinear edges as we go (every vertex has degree 2, since the
    # union has no holes).
    adjacency: dict[tuple[float, float], list[tuple[float, float]]] = {}
    for a, b in raw_edges:
        adjacency.setdefault(a, []).append(b)

    def direction(a, b):
        return (
            0 if b[0] == a[0] else (1 if b[0] > a[0] else -1),
            0 if b[1] == a[1] else (1 if b[1] > a[1] else -1),
        )

    start = raw_edges[0][0]
    loop = [start]
    current = start
    prev_dir = None
    for _ in range(len(raw_edges)):
        nxt = adjacency[current].pop(0)
        if not adjacency[current]:
            del adjacency[current]
        d = direction(current, nxt)
        if d == prev_dir:
            loop[-1] = nxt
        else:
            loop.append(nxt)
        prev_dir = d
        current = nxt

    if loop[-1] == loop[0]:
        loop.pop()
    return [(loop[i], loop[(i + 1) % len(loop)]) for i in range(len(loop))]
