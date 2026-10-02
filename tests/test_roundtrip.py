"""Перевод A → B → A для всех пар представлений возвращает исходный граф."""

from collections import Counter
from itertools import product

import pytest

from formatters import serialize
from graph import Format, Graph, GraphError
from parsers import parse_graph
from samples import GRAPHS

PAIRS = list(product(Format, Format))
PAIR_IDS = [f"{a.value}->{b.value}" for a, b in PAIRS]


def rebuild(graph: Graph, fmt: Format) -> Graph:
    """Граф, построенный заново из представления ``fmt`` графа ``graph`` (Python API)."""
    kw = dict(directed=graph.directed)
    if fmt is Format.EDGE_LIST:
        return Graph.from_edge_list(graph.to_edge_list(), graph.vertices, weighted=graph.weighted, **kw)
    if fmt is Format.ADJACENCY_MATRIX:
        return Graph.from_adjacency_matrix(
            graph.to_adjacency_matrix(), graph.vertices, weighted=graph.weighted, **kw
        )
    if fmt is Format.ADJACENCY_LIST:
        return Graph.from_adjacency_list(graph.to_adjacency_list(), weighted=graph.weighted, **kw)
    weights = graph.edge_weights if graph.weighted else None
    return Graph.from_incidence_matrix(graph.to_incidence_matrix(), graph.vertices, weights, **kw)


def rebuild_text(graph: Graph, fmt: Format) -> Graph:
    """То же через текст: запись в формате ввода и обратный разбор."""
    return parse_graph(serialize(graph, fmt), fmt, directed=graph.directed, weighted=graph.weighted)


def canonical(graph: Graph, fmt: Format):
    """Представление ``fmt`` с точностью до порядка рёбер (порядок вершин важен)."""
    if fmt is Format.ADJACENCY_MATRIX:
        return graph.vertices, graph.to_adjacency_matrix()
    if fmt is Format.ADJACENCY_LIST:
        return [(v, Counter(n)) for v, n in graph.to_adjacency_list().items()]
    if fmt is Format.INCIDENCE_MATRIX:
        columns = zip(*graph.to_incidence_matrix()) if graph.edge_count else []
        return graph.vertices, Counter(zip(columns, graph.edge_weights))
    if graph.directed:
        return graph.vertices, Counter(graph.edges)
    return graph.vertices, Counter((frozenset((u, v)), w) for u, v, w in graph.edges)


@pytest.mark.parametrize("name", GRAPHS)
@pytest.mark.parametrize(("src", "dst"), PAIRS, ids=PAIR_IDS)
@pytest.mark.parametrize("via", [rebuild, rebuild_text], ids=["api", "text"])
def test_a_to_b_to_a(name, src, dst, via):
    original = GRAPHS[name]()
    a = via(original, src)   # граф, заданный в представлении A
    b = via(a, dst)          # A → B
    back = via(b, src)       # B → A

    assert back == original
    assert back.vertices == original.vertices
    assert canonical(back, src) == canonical(original, src)


@pytest.mark.parametrize("name", GRAPHS)
@pytest.mark.parametrize("fmt", list(Format), ids=lambda f: f.value)
def test_text_is_stable(name, fmt):
    """Записанный и прочитанный граф при повторной записи даёт тот же текст.

    Первая запись может переставить рёбра (у неориентированного графа ребро
    хранится один раз, и порядок соседей в списке смежности меняется), но
    дальше текст уже не меняется.
    """
    once = rebuild_text(GRAPHS[name](), fmt)
    twice = rebuild_text(once, fmt)
    assert serialize(twice, fmt) == serialize(once, fmt)


def test_weighted_multigraph_roundtrips_except_adjacency_matrix():
    graph = Graph.from_edge_list([(1, 2, 5), (1, 2, 7), (2, 3, 1)], weighted=True)
    with pytest.raises(GraphError, match="кратные"):
        graph.to_adjacency_matrix()
    for src, dst in product(Format, Format):
        if Format.ADJACENCY_MATRIX in (src, dst):
            continue
        for via in (rebuild, rebuild_text):
            assert via(via(via(graph, src), dst), src) == graph
