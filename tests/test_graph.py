"""Построение графа из каждого представления, вывод в каждое и проверки корректности."""

import pytest

from graph import Format, Graph, GraphError

# Треугольник 1–2–3 с «хвостом» 3–4.
TRIANGLE_EDGES = [(1, 2), (2, 3), (3, 1), (3, 4)]
TRIANGLE_MATRIX = [
    [0, 1, 1, 0],
    [1, 0, 1, 0],
    [1, 1, 0, 1],
    [0, 0, 1, 0],
]
TRIANGLE_LIST = {1: [2, 3], 2: [1, 3], 3: [2, 1, 4], 4: [3]}
TRIANGLE_INCIDENCE = [
    [1, 0, 1, 0],
    [1, 1, 0, 0],
    [0, 1, 1, 1],
    [0, 0, 0, 1],
]


@pytest.fixture
def triangle() -> Graph:
    return Graph.from_edge_list(TRIANGLE_EDGES)


# ---------------------------------------------------------------------- #
# Неориентированный невзвешенный граф: все четыре представления
# ---------------------------------------------------------------------- #

def test_to_all_representations(triangle):
    assert triangle.vertices == [1, 2, 3, 4]
    assert triangle.to_edge_list() == TRIANGLE_EDGES
    assert triangle.to_adjacency_matrix() == TRIANGLE_MATRIX
    assert triangle.to_adjacency_list() == TRIANGLE_LIST
    assert triangle.to_incidence_matrix() == TRIANGLE_INCIDENCE


def test_from_all_representations_give_same_graph(triangle):
    assert Graph.from_adjacency_matrix(TRIANGLE_MATRIX) == triangle
    assert Graph.from_adjacency_list(TRIANGLE_LIST) == triangle
    assert Graph.from_incidence_matrix(TRIANGLE_INCIDENCE) == triangle


def test_matrix_vertices_default_to_one_based(triangle):
    assert Graph.from_adjacency_matrix(TRIANGLE_MATRIX).vertices == [1, 2, 3, 4]
    assert Graph.from_incidence_matrix(TRIANGLE_INCIDENCE).vertices == [1, 2, 3, 4]


def test_custom_vertex_names():
    g = Graph.from_adjacency_matrix([[0, 1], [1, 0]], vertices=["x", "y"])
    assert g.vertices == ["x", "y"]
    assert g.to_edge_list() == [("x", "y")]


def test_neighbors(triangle):
    assert triangle.neighbors(3) == [2, 1, 4]
    with pytest.raises(GraphError, match="нет в графе"):
        triangle.neighbors(99)


# ---------------------------------------------------------------------- #
# Ориентированные и взвешенные графы
# ---------------------------------------------------------------------- #

def test_directed_weighted_representations():
    g = Graph.from_edge_list([("A", "B", 4), ("B", "C", 2), ("C", "A", 7)],
                             directed=True, weighted=True)
    assert g.to_adjacency_matrix() == [[0, 4, 0], [0, 0, 2], [7, 0, 0]]
    assert g.to_adjacency_list() == {"A": [("B", 4)], "B": [("C", 2)], "C": [("A", 7)]}
    assert g.to_incidence_matrix() == [[-1, 0, 1], [1, -1, 0], [0, 1, -1]]
    assert g.edge_weights == [4, 2, 7]


def test_directed_matrix_is_not_symmetric():
    g = Graph.from_adjacency_matrix([[0, 1], [0, 0]], directed=True)
    assert g.to_edge_list() == [(1, 2)]
    assert g != Graph.from_adjacency_matrix([[0, 0], [1, 0]], directed=True)


def test_from_incidence_with_weights():
    g = Graph.from_incidence_matrix([[-1, 0], [1, -1], [0, 1]], weights=[5, 2.5], directed=True)
    assert g.weighted
    assert g.to_edge_list() == [(1, 2, 5), (2, 3, 2.5)]


def test_undirected_weighted_matrix():
    g = Graph.from_adjacency_matrix([[0, 3], [3, 0]], weighted=True)
    assert g.to_edge_list() == [(1, 2, 3)]


def test_negative_and_fractional_weights():
    g = Graph.from_edge_list([(1, 2, -3), (2, 3, 0.25)], weighted=True)
    assert g.to_adjacency_matrix() == [[0, -3, 0], [-3, 0, 0.25], [0, 0.25, 0]]


# ---------------------------------------------------------------------- #
# Петли, кратные рёбра, изолированные вершины
# ---------------------------------------------------------------------- #

def test_loop_undirected():
    g = Graph.from_edge_list([(1, 1), (1, 2)])
    assert g.to_adjacency_matrix() == [[1, 1], [1, 0]]
    assert g.to_adjacency_list() == {1: [1, 2], 2: [1]}  # петля — один раз
    assert g.to_incidence_matrix() == [[2, 1], [0, 1]]


def test_loop_directed():
    g = Graph.from_edge_list([(1, 1)], directed=True)
    assert g.to_incidence_matrix() == [[2]]
    assert Graph.from_incidence_matrix([[2]], directed=True) == g


def test_parallel_edges_unweighted_counted_in_matrix():
    g = Graph.from_edge_list([(1, 2), (2, 1), (1, 2)])
    assert g.has_parallel_edges()
    assert g.to_adjacency_matrix() == [[0, 3], [3, 0]]
    assert Graph.from_adjacency_matrix([[0, 3], [3, 0]]).edge_count == 3


def test_opposite_arcs_are_not_parallel():
    assert not Graph.from_edge_list([(1, 2), (2, 1)], directed=True).has_parallel_edges()
    assert Graph.from_edge_list([(1, 2), (2, 1)]).has_parallel_edges()


def test_weighted_parallel_edges_not_in_adjacency_matrix():
    g = Graph.from_edge_list([(1, 2, 5), (2, 1, 6)], weighted=True)
    with pytest.raises(GraphError, match="кратные"):
        g.to_adjacency_matrix()


def test_zero_weight_not_in_adjacency_matrix():
    g = Graph.from_edge_list([(1, 2, 0)], weighted=True)
    with pytest.raises(GraphError, match="вес 0"):
        g.to_adjacency_matrix()


def test_isolated_vertices_kept():
    g = Graph.from_edge_list([(1, 2)], vertices=[1, 2, 3])
    assert g.to_adjacency_matrix() == [[0, 1, 0], [1, 0, 0], [0, 0, 0]]
    assert g.to_adjacency_list() == {1: [2], 2: [1], 3: []}
    assert g.to_incidence_matrix() == [[1], [1], [0]]


# ---------------------------------------------------------------------- #
# Равенство
# ---------------------------------------------------------------------- #

def test_equality_ignores_order_and_direction_of_undirected_edges():
    a = Graph.from_edge_list([(1, 2), (2, 3)])
    b = Graph.from_edge_list([(3, 2), (2, 1)])
    assert a == b


def test_equality_respects_type_and_multiplicity():
    base = Graph.from_edge_list([(1, 2)])
    assert base != Graph.from_edge_list([(1, 2)], directed=True)
    assert base != Graph.from_edge_list([(1, 2, 1)], weighted=True)
    assert base != Graph.from_edge_list([(1, 2), (1, 2)])
    assert base != Graph.from_edge_list([(1, 2)], vertices=[1, 2, 3])


def test_repr():
    assert "вершин: 4" in repr(Graph.from_edge_list(TRIANGLE_EDGES))


def test_format_titles():
    assert [f.title for f in Format] == [
        "Список рёбер", "Матрица смежности", "Список смежности", "Матрица инцидентности",
    ]


# ---------------------------------------------------------------------- #
# Проверка некорректных данных
# ---------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("matrix", "kwargs", "message"),
    [
        ([[0, 1], [1]], {}, "квадратной"),
        ([[0, 1, 0], [1, 0, 1]], {}, "квадратной"),
        ([[0, 1], [0, 0]], {}, "несимметрична"),
        ([[0, 2], [3, 0]], {"weighted": True}, "несимметрична"),
        ([[0, 0.5], [0.5, 0]], {}, "неотрицательные целые"),
        ([[0, -1], [-1, 0]], {}, "неотрицательные целые"),
        ([[0, "x"], ["x", 0]], {}, "ожидалось число"),
        ([[0, True], [True, 0]], {}, "ожидалось число"),
        ([[0, float("inf")], [float("inf"), 0]], {"weighted": True}, "конечным"),
        ([[0, 1], [1, 0]], {"vertices": ["a"]}, "имён вершин"),
        ([[0, 1], [1, 0]], {"vertices": ["a", "a"]}, "дважды"),
    ],
)
def test_adjacency_matrix_validation(matrix, kwargs, message):
    with pytest.raises(GraphError, match=message):
        Graph.from_adjacency_matrix(matrix, **kwargs)


@pytest.mark.parametrize(
    ("matrix", "kwargs", "message"),
    [
        ([[1, 0], [1]], {}, "разное число столбцов"),
        ([[1], [1], [1]], {}, "две единицы"),             # ребро на трёх вершинах
        ([[1], [0]], {}, "две единицы"),                  # висячее ребро
        ([[0], [0]], {}, "только нули"),                  # пустой столбец
        ([[2], [1]], {}, "две единицы"),
        ([[-1], [1]], {}, "недопустимо"),                 # -1 в неориентированном
        ([[3], [0]], {"directed": True}, "недопустимо"),
        ([[1], [1]], {"directed": True}, "одна -1"),      # нет начала дуги
        ([[-1], [-1]], {"directed": True}, "одна -1"),
        ([[1], [1]], {"weights": [1, 2]}, "весов 2"),
        ([[1], [1]], {"weights": ["x"]}, "ожидалось число"),
        ([[1], [1]], {"vertices": [1, 2, 3]}, "имён вершин"),
    ],
)
def test_incidence_matrix_validation(matrix, kwargs, message):
    with pytest.raises(GraphError, match=message):
        Graph.from_incidence_matrix(matrix, **kwargs)


def test_adjacency_list_must_be_symmetric_for_undirected():
    with pytest.raises(GraphError, match="обоих концов"):
        Graph.from_adjacency_list({1: [2], 2: []})
    with pytest.raises(GraphError, match="обоих концов"):
        Graph.from_adjacency_list({1: [], 2: [1]})
    with pytest.raises(GraphError, match="обоих концов"):
        Graph.from_adjacency_list({1: [(2, 5)], 2: [(1, 6)]}, weighted=True)
    with pytest.raises(GraphError, match="обоих концов"):
        Graph.from_adjacency_list({1: [2, 2], 2: [1]})
    # в ориентированном графе это нормально
    assert Graph.from_adjacency_list({1: [2], 2: []}, directed=True).edge_count == 1


def test_adjacency_list_unknown_vertex():
    with pytest.raises(GraphError, match="такой вершины нет"):
        Graph.from_adjacency_list({1: [2]}, directed=True)


def test_adjacency_list_weighted_item_shape():
    with pytest.raises(GraphError, match=r"\(вершина, вес\)"):
        Graph.from_adjacency_list({1: [2], 2: [1]}, weighted=True)


@pytest.mark.parametrize(
    ("edges", "kwargs", "message"),
    [
        ([(1,)], {}, "ожидалась пара"),
        ([(1, 2, 3)], {}, "граф невзвешенный"),
        ([(1, 2)], {"weighted": True}, r"\(u, v, вес\)"),
        ([(1, 2, "a")], {"weighted": True}, "ожидалось число"),
        ([(1, 5)], {"vertices": [1, 2]}, "несуществующую вершину 5"),
        ([([1], 2)], {}, "хешируемым"),
    ],
)
def test_edge_list_validation(edges, kwargs, message):
    with pytest.raises(GraphError, match=message):
        Graph.from_edge_list(edges, **kwargs)


def test_add_edge_weight_rules():
    g = Graph()
    with pytest.raises(GraphError, match="граф невзвешенный"):
        g.add_edge(1, 2, 5)
    w = Graph(weighted=True)
    with pytest.raises(GraphError, match="не указан вес"):
        w.add_edge(1, 2)
