"""Набор графов для тестов: все сочетания типов, петли, кратные рёбра, изолированные вершины."""

from graph import Graph


def undirected_simple() -> Graph:
    return Graph.from_edge_list([(1, 2), (2, 3), (3, 1), (3, 4)])


def undirected_weighted_with_loop_and_isolated() -> Graph:
    return Graph.from_edge_list(
        [("a", "b", 3), ("b", "c", 2.5), ("c", "c", 7), ("a", "c", -1)],
        vertices=["a", "b", "c", "z"],
        weighted=True,
    )


def undirected_multigraph() -> Graph:
    return Graph.from_edge_list([(1, 2), (2, 1), (2, 3), (3, 3), (3, 3)], vertices=[1, 2, 3, 4])


def directed_simple() -> Graph:
    return Graph.from_edge_list([(1, 2), (2, 1), (2, 3), (4, 3)], directed=True)


def directed_weighted_with_loop() -> Graph:
    return Graph.from_edge_list(
        [("A", "B", 4), ("B", "A", 6), ("B", "C", 0.5), ("C", "C", 2), ("C", "A", 10)],
        vertices=["C", "A", "B", "D"],  # порядок вершин не совпадает с порядком появления
        directed=True,
        weighted=True,
    )


def directed_multigraph() -> Graph:
    return Graph.from_edge_list([(1, 2), (1, 2), (2, 1), (2, 2)], directed=True)


def single_vertex_no_edges() -> Graph:
    return Graph.from_edge_list([], vertices=["solo"])


def edgeless_weighted() -> Graph:
    return Graph.from_edge_list([], vertices=[1, 2, 3], weighted=True, directed=True)


GRAPHS = {
    f.__name__: f
    for f in [
        undirected_simple,
        undirected_weighted_with_loop_and_isolated,
        undirected_multigraph,
        directed_simple,
        directed_weighted_with_loop,
        directed_multigraph,
        single_vertex_no_edges,
        edgeless_weighted,
    ]
}
