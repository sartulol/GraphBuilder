"""Вывод на экран и запись в текстовый формат."""

import pytest

from formatters import (
    describe,
    format_number,
    format_table,
    plural,
    pretty,
    pretty_all,
    serialize,
    vertex_name,
)
from graph import Format, Graph, GraphError


@pytest.fixture
def weighted_directed() -> Graph:
    return Graph.from_edge_list([("a", "b", 4), ("b", "c", 2.5)], directed=True, weighted=True)


def test_format_number():
    assert format_number(3) == "3"
    assert format_number(3.0) == "3"
    assert format_number(2.5) == "2.5"
    assert format_number(-0.125) == "-0.125"


def test_plural():
    assert plural(1, "вершина", "вершины", "вершин") == "1 вершина"
    assert plural(3, "вершина", "вершины", "вершин") == "3 вершины"
    assert plural(5, "вершина", "вершины", "вершин") == "5 вершин"
    assert plural(11, "вершина", "вершины", "вершин") == "11 вершин"
    assert plural(21, "вершина", "вершины", "вершин") == "21 вершина"
    assert plural(112, "вершина", "вершины", "вершин") == "112 вершин"


def test_describe(weighted_directed):
    assert describe(weighted_directed) == "Ориентированный взвешенный граф: 3 вершины, 2 дуги"
    assert describe(Graph.from_edge_list([(1, 2)])) == (
        "Неориентированный невзвешенный граф: 2 вершины, 1 ребро"
    )


def test_format_table_alignment():
    table = format_table(["a", "long"], ["1", "22"], [["0", "1"], ["10", "0"]])
    assert table.splitlines() == [
        "     │  1 22",
        "─────┼──────",
        "   a │  0  1",
        "long │ 10  0",
    ]


def test_format_table_extra_rows():
    table = format_table(["1", "2"], ["e1"], [["1"], ["1"]], [("вес", ["7"])])
    lines = table.splitlines()
    assert lines[-1] == "вес │  7"
    assert lines[-2].startswith("────┼")


def test_pretty_adjacency_matrix_has_row_and_column_labels():
    g = Graph.from_edge_list([("x", "y")])
    text = pretty(g, Format.ADJACENCY_MATRIX)
    assert text.splitlines()[:5] == [
        "── Матрица смежности ──",
        "  │ x y",
        "──┼────",
        "x │ 0 1",
        "y │ 1 0",
    ]


def test_pretty_incidence_with_weights_and_legend(weighted_directed):
    text = pretty(weighted_directed, Format.INCIDENCE_MATRIX)
    assert "  a │ -1   0" in text  # второй столбец шире из-за веса 2.5
    assert "вес │  4 2.5" in text
    assert "e1 = a → b, e2 = b → c" in text


def test_pretty_edge_and_adjacency_lists(weighted_directed):
    edges = pretty(weighted_directed, Format.EDGE_LIST)
    assert "1. a → b  (вес 4)" in edges
    adjacency = pretty(weighted_directed, Format.ADJACENCY_LIST)
    assert "a → b(4)" in adjacency
    assert "c → ∅" in adjacency


def test_pretty_reports_isolated_vertices():
    g = Graph.from_edge_list([(1, 2)], vertices=[1, 2, 3])
    assert "Изолированные вершины: 3" in pretty(g, Format.EDGE_LIST)


def test_pretty_explains_impossible_representation():
    g = Graph.from_edge_list([(1, 2, 1), (1, 2, 2)], weighted=True)
    text = pretty(g, Format.ADJACENCY_MATRIX)
    assert text.startswith("── Матрица смежности ──\nНевозможно построить:")


def test_pretty_all_contains_every_format(weighted_directed):
    text = pretty_all(weighted_directed)
    for fmt in Format:
        assert fmt.title in text


def test_serialize_examples():
    g = Graph.from_edge_list([("a", "b", 4), ("b", "c", 2.5)], vertices=["a", "b", "c", "d"],
                             weighted=True)
    assert serialize(g, Format.EDGE_LIST) == "V: a b c d\na b 4\nb c 2.5\n"
    assert serialize(g, Format.ADJACENCY_MATRIX) == (
        "V: a b c d\n"
        "0   4   0 0\n"
        "4   0 2.5 0\n"
        "0 2.5   0 0\n"
        "0   0   0 0\n"
    )
    assert serialize(g, Format.ADJACENCY_LIST) == "a: b(4)\nb: a(4) c(2.5)\nc: b(2.5)\nd:\n"
    assert serialize(g, Format.INCIDENCE_MATRIX) == (
        "V: a b c d\n1 0\n1 1\n0 1\n0 0\nW: 4 2.5\n"
    )


def test_serialize_omits_vertex_line_when_not_needed():
    g = Graph.from_edge_list([(1, 2), (2, 3)])
    assert serialize(g, Format.EDGE_LIST) == "1 2\n2 3\n"
    assert serialize(g, Format.ADJACENCY_MATRIX).startswith("0 1 0\n")


def test_vertex_name_rejects_unwritable_names():
    assert vertex_name("Москва") == "Москва"
    for bad in ("two words", "a:b", "x(1)", "", "a,b"):
        with pytest.raises(GraphError):
            vertex_name(bad)
    with pytest.raises(GraphError, match="превратится"):
        vertex_name("7")  # строка "7" прочиталась бы как число
    with pytest.raises(GraphError, match="стрелки"):
        vertex_name("->")  # в списке рёбер это стрелка, а не вершина
