"""Отрисовка графа с помощью networkx (раскладка, вершины) и matplotlib (рёбра).

Рёбра рисуются вручную, чтобы корректно показывать то, что стандартная
отрисовка networkx склеивает: кратные рёбра и встречные дуги (разводятся
дугами), петли (рисуются «ушком» над вершиной, несколько петель — вложенно).
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyArrowPatch
from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath

from formatters import describe, format_number
from graph import Graph, Vertex

LAYOUTS = ("spring", "circular", "shell", "spectral")

NODE_COLOR = "#dbe8f6"
NODE_EDGE_COLOR = "#2b5d8a"
EDGE_COLOR = "#3c4650"
LABEL_BOX = dict(boxstyle="round,pad=0.2", fc="white", ec="#c0c6cc", lw=0.6, alpha=0.95)
LABEL_FONT_SIZE = 11       # подписи вершин, pt
MIN_LABEL_FONT_SIZE = 7
MAX_LABEL_WIDTH = 60       # шире — подпись набирается мельче, pt
MIN_NODE_RADIUS = 15       # pt
EDGE_FONT_SIZE = 10        # веса рёбер, pt
CURVE_STEP = 0.3           # насколько сильнее изгибается каждое следующее кратное ребро
LOOP_HEIGHT = 34           # высота петли над кружком вершины, pt
LOOP_GROWTH = 0.6          # каждая следующая петля у той же вершины выше на эту долю
PADDING = 14               # поле вокруг рисунка сверх радиуса вершин, pt


def to_networkx(graph: Graph) -> nx.MultiGraph | nx.MultiDiGraph:
    """Граф networkx с теми же вершинами и рёбрами (вес — атрибут ``weight``)."""
    g = nx.MultiDiGraph() if graph.directed else nx.MultiGraph()
    g.add_nodes_from(graph.vertices)
    for u, v, w in graph.edges:
        g.add_edge(u, v, weight=w)
    return g


def compute_layout(graph: Graph, layout: str = "spring", seed: int = 42) -> dict[Vertex, tuple[float, float]]:
    """Координаты вершин для выбранной раскладки networkx.

    ``circular`` и ``shell`` раскладывают весь граф целиком. ``spring`` и
    ``spectral`` раскладывают каждую компоненту связности отдельно и укладывают
    компоненты рядами — иначе изолированные вершины отталкивают остальные и
    сжимают основную часть графа.
    """
    if layout not in LAYOUTS:
        raise ValueError(f"неизвестная раскладка {layout!r}, доступны: {', '.join(LAYOUTS)}")
    simple = nx.Graph()
    simple.add_nodes_from(graph.vertices)
    simple.add_edges_from((u, v) for u, v, _ in graph.edges if u != v)
    if simple.number_of_nodes() == 0:
        return {}
    if layout == "circular":
        return _as_floats(nx.circular_layout(simple))
    if layout == "shell":
        return _as_floats(nx.shell_layout(simple))

    order = {v: i for i, v in enumerate(graph.vertices)}
    components = sorted(
        (sorted(c, key=order.__getitem__) for c in nx.connected_components(simple)),
        key=lambda c: (-len(c), order[c[0]]),
    )
    return _pack_components(
        [_component_layout(simple.subgraph(c), layout, seed) for c in components]
    )


def _as_floats(pos) -> dict[Vertex, tuple[float, float]]:
    return {v: (float(x), float(y)) for v, (x, y) in pos.items()}


def _component_layout(sub: nx.Graph, layout: str, seed: int) -> dict[Vertex, tuple[float, float]]:
    """Раскладка одной компоненты, вписанная в квадрат со стороной ~√n."""
    n = sub.number_of_nodes()
    if n == 1:
        return {next(iter(sub)): (0.0, 0.0)}
    if n == 2:
        a, b = sub
        return {a: (-0.5, 0.0), b: (0.5, 0.0)}
    if layout == "spectral":
        pos = nx.spectral_layout(sub)
    else:
        pos = nx.spring_layout(sub, seed=seed)
    pos = _as_floats(pos)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    extent = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    size = n ** 0.5
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return {v: ((x - cx) / extent * size, (y - cy) / extent * size) for v, (x, y) in pos.items()}


def _pack_components(layouts: list[dict[Vertex, tuple[float, float]]]) -> dict[Vertex, tuple[float, float]]:
    """Укладывает компоненты (крупные первыми) рядами слева направо."""
    gap = 1.0
    boxes = []
    for pos in layouts:
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        boxes.append((min(xs), max(xs), min(ys), max(ys)))
    widths = [x1 - x0 for x0, x1, _, _ in boxes]
    row_width = max(max(widths), (sum((w + gap) ** 2 for w in widths)) ** 0.5)

    result: dict[Vertex, tuple[float, float]] = {}
    x = y = row_height = 0.0
    for pos, (x0, x1, y0, y1) in zip(layouts, boxes):
        if x > 0 and x + (x1 - x0) > row_width:
            x, y, row_height = 0.0, y - row_height - gap, 0.0
        for v, (px, py) in pos.items():
            result[v] = (x + px - x0, y - (y1 - py))
        x += (x1 - x0) + gap
        row_height = max(row_height, y1 - y0)
    return result


def _node_labels(graph: Graph) -> dict[Vertex, tuple[float, float]]:
    """Для каждой вершины — (размер шрифта подписи, радиус кружка в пунктах).

    Кружок подстраивается под ширину подписи; слишком длинные подписи
    набираются меньшим шрифтом, чтобы вершины не становились огромными.
    """
    result = {}
    for v in graph.vertices:
        font_size = LABEL_FONT_SIZE
        width = _text_width_pt(_label_text(v), font_size)
        if width > MAX_LABEL_WIDTH:
            font_size = max(MIN_LABEL_FONT_SIZE, font_size * MAX_LABEL_WIDTH / width)
            width = _text_width_pt(_label_text(v), font_size)
        result[v] = (font_size, max(MIN_NODE_RADIUS, width / 2 + 6))
    return result


def _free_direction(
    pos: dict[Vertex, tuple[float, float]], v: Vertex, groups: dict[frozenset, list]
) -> tuple[float, float]:
    """Единичный вектор от вершины в сторону, где дальше всего до её рёбер.

    Перебираются 8 направлений; при равенстве предпочитается «вверх».
    """
    x, y = pos[v]
    angles = []
    for pair in groups:
        if v in pair:
            (other,) = pair - {v}
            ox, oy = pos[other]
            if (ox, oy) != (x, y):
                angles.append(math.atan2(oy - y, ox - x))
    if not angles:
        return 0.0, 1.0

    def clearance(a: float) -> float:
        return min(abs((a - b + math.pi) % (2 * math.pi) - math.pi) for b in angles)

    up = math.pi / 2
    candidates = [up + k * math.pi / 4 for k in range(8)]  # «вверх» первым
    best = max(candidates, key=lambda a: round(clearance(a), 6))
    return math.cos(best), math.sin(best)


def _label_text(v: Vertex) -> str:
    """Подпись вершины; ``$`` экранируется, иначе matplotlib разберёт имя как формулу."""
    return str(v).replace("$", r"\$")


def _text_width_pt(text: str, font_size: float) -> float:
    prop = FontProperties(size=font_size, weight="bold")
    return TextPath((0, 0), text, prop=prop).get_extents().width


def draw_graph(
    graph: Graph,
    *,
    layout: str = "spring",
    title: str | None = None,
    save_path: str | Path | None = None,
    show: bool = True,
    seed: int = 42,
) -> Figure:
    """Рисует граф: подписи вершин, веса на рёбрах, стрелки у дуг.

    Args:
        graph: граф.
        layout: раскладка вершин — ``spring``, ``circular``, ``shell``, ``spectral``.
        title: заголовок; по умолчанию — описание графа.
        save_path: если задан, рисунок сохраняется в этот файл (PNG, SVG, PDF...).
        show: открыть окно с рисунком (блокирует до закрытия окна).
        seed: зерно случайной раскладки ``spring`` — одинаковый граф рисуется одинаково.

    Returns:
        Фигура matplotlib (если ``show=False``, её можно сохранить или закрыть).
    """
    pos = compute_layout(graph, layout, seed)
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.set_title(title or describe(graph), fontsize=12)
    ax.set_aspect("equal")
    ax.axis("off")

    labels = _node_labels(graph)
    radius = {v: r for v, (_, r) in labels.items()}  # pt
    loops_by_vertex: dict[Vertex, list[float]] = defaultdict(list)
    for u, v, w in graph.edges:
        if u == v:
            loops_by_vertex[u].append(w)

    def loop_height(v: Vertex, k: int) -> float:
        """Высота k-й петли вершины над её центром, pt."""
        return radius[v] + LOOP_HEIGHT * (1 + LOOP_GROWTH * k)

    # Масштаб (единиц данных на пункт) подбираем так, чтобы вокруг вершин
    # осталось поле в пунктах: кружки и петли не обрезаются при любом размере.
    fig.tight_layout()
    box = ax.get_window_extent()
    width_pt, height_pt = box.width * 72 / fig.dpi, box.height * 72 / fig.dpi
    # петля может смотреть в любую сторону — поле одинаковое со всех сторон
    pad = PADDING + max(
        [MIN_NODE_RADIUS, *radius.values()]
        + [loop_height(v, len(ws) - 1) for v, ws in loops_by_vertex.items()]
    )
    xs = [p[0] for p in pos.values()] or [0.0]
    ys = [p[1] for p in pos.values()] or [0.0]
    scale = max(
        (max(xs) - min(xs)) / max(width_pt - 2 * pad, 1.0),
        (max(ys) - min(ys)) / max(height_pt - 2 * pad, 1.0),
        1e-3,  # одна вершина: масштаб произвольный
    )
    ax.set_xlim(min(xs) - pad * scale, max(xs) + pad * scale)
    ax.set_ylim(min(ys) - pad * scale, max(ys) + pad * scale)

    arrowstyle = "-|>" if graph.directed else "-"
    index = {v: i for i, v in enumerate(graph.vertices)}

    # --- обычные рёбра: группируем по паре концов, кратные разводим дугами ---
    groups: dict[frozenset, list[tuple[Vertex, Vertex, float]]] = defaultdict(list)
    for u, v, w in graph.edges:
        if u != v:
            groups[frozenset((u, v))].append((u, v, w))

    for edges in groups.values():
        a, b = sorted({edges[0][0], edges[0][1]}, key=index.__getitem__)
        (ax_, ay), (bx, by) = pos[a], pos[b]
        dx, dy = bx - ax_, by - ay
        total = len(edges)
        for k, (u, v, w) in enumerate(edges):
            # смещение в «каноническом» направлении a → b; у дуги b → a знак
            # rad меняется, чтобы она легла на ту же сторону, что и рассчитано
            offset = (k - (total - 1) / 2) * CURVE_STEP
            rad = offset if u == a else -offset
            ax.add_patch(FancyArrowPatch(
                pos[u], pos[v],
                connectionstyle=f"arc3,rad={rad}",
                arrowstyle=arrowstyle,
                mutation_scale=20,
                shrinkA=radius[u] + 1,
                shrinkB=radius[v] + 2,
                color=EDGE_COLOR,
                linewidth=1.6,
                zorder=1,
            ))
            if graph.weighted:
                # середина квадратичной кривой Безье arc3
                lx = ax_ + dx / 2 + offset * dy / 2
                ly = ay + dy / 2 - offset * dx / 2
                ax.text(lx, ly, format_number(w), ha="center", va="center",
                        fontsize=EDGE_FONT_SIZE, bbox=LABEL_BOX, zorder=4)

    # --- петли: «ушко» в самую свободную сторону, каждая следующая длиннее ---
    for v, weights in loops_by_vertex.items():
        x, y = pos[v]
        r = radius[v] * scale
        dx, dy = _free_direction(pos, v, groups)
        px, py = dy, -dx  # перпендикуляр к направлению петли

        def point(along: float, across: float) -> tuple[float, float]:
            return x + along * dx + across * px, y + along * dy + across * py

        for k, w in enumerate(weights):
            height = loop_height(v, k) * scale
            # начало и конец — на окружности вершины по обе стороны от направления петли;
            # вершина кубической кривой Безье — на 0.25·(0.8r) + 0.75·control
            control = (height - 0.2 * r) / 0.75
            half = max(r, height * 0.45)
            path = MplPath(
                [point(0.8 * r, -0.6 * r), point(control, -half),
                 point(control, half), point(0.8 * r, 0.6 * r)],
                [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4],
            )
            ax.add_patch(FancyArrowPatch(
                path=path, arrowstyle=arrowstyle, mutation_scale=18,
                color=EDGE_COLOR, linewidth=1.6, zorder=1,
            ))
            if graph.weighted:
                ax.text(*point(height, 0), format_number(w), ha="center", va="center",
                        fontsize=EDGE_FONT_SIZE, bbox=LABEL_BOX, zorder=4)

    # --- вершины (networkx) и их подписи ---
    nodes = nx.draw_networkx_nodes(
        to_networkx(graph), pos, ax=ax,
        node_size=[(2 * radius[v]) ** 2 for v in graph.vertices],  # площадь маркера, pt²
        nodelist=graph.vertices, node_color=NODE_COLOR,
        edgecolors=NODE_EDGE_COLOR, linewidths=1.8,
    ) if graph.vertices else None
    if nodes is not None:
        nodes.set_zorder(2)
    for v, (font_size, _) in labels.items():
        ax.text(*pos[v], _label_text(v), ha="center", va="center", fontsize=font_size,
                fontweight="bold", zorder=3)

    if save_path is not None:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    return fig
