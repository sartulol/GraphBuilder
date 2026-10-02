"""Разбор текстового ввода: форматы, комментарии, разделители и сообщения об ошибках."""

import pytest

from conftest import EXAMPLES
from graph import Format, Graph, GraphError
from parsers import (
    ParseError,
    parse_adjacency_list,
    parse_adjacency_matrix,
    parse_edge_list,
    parse_graph,
    parse_incidence_matrix,
    parse_number,
    parse_vertex,
    read_graph,
)


# ---------------------------------------------------------------------- #
# Примитивы
# ---------------------------------------------------------------------- #

def test_parse_vertex():
    assert parse_vertex("12") == 12
    assert parse_vertex("-3") == -3
    assert parse_vertex("A") == "A"
    assert parse_vertex("Москва") == "Москва"
    with pytest.raises(ParseError, match="недопустимые символы"):
        parse_vertex("a(b")


@pytest.mark.parametrize("arrow", ["-", "->", "—", "→"])
def test_parse_vertex_rejects_arrow_tokens(arrow):
    # в списке рёбер такой токен — стрелка, вершину с этим именем не прочитать
    with pytest.raises(ParseError, match="знаком стрелки"):
        parse_vertex(arrow)
    with pytest.raises(ParseError, match="знаком стрелки"):
        parse_edge_list(f"V: {arrow} a\n")


def test_parse_number():
    assert parse_number("7") == 7 and isinstance(parse_number("7"), int)
    assert parse_number("2.5") == 2.5
    assert parse_number("3.0") == 3 and isinstance(parse_number("3.0"), int)
    assert parse_number("-1e3") == -1000
    for bad in ("abc", "nan", "inf", "1,5"):
        with pytest.raises(ParseError):
            parse_number(bad)


# ---------------------------------------------------------------------- #
# Список рёбер
# ---------------------------------------------------------------------- #

def test_edge_list_basic_with_comments_and_separators():
    text = """
    # комментарий
    1 2        # ребро 1–2
    2,3
    3;1
    """
    assert parse_edge_list(text) == Graph.from_edge_list([(1, 2), (2, 3), (3, 1)])


@pytest.mark.parametrize("arrow", ["-", "->", "—", "→"])
def test_edge_list_arrows(arrow):
    g = parse_edge_list(f"a {arrow} b", directed=True)
    assert g.to_edge_list() == [("a", "b")]


def test_edge_list_negative_weight_is_not_arrow():
    assert parse_edge_list("a b -5", weighted=True).to_edge_list() == [("a", "b", -5)]


def test_edge_list_vertex_line_adds_isolated_and_sets_order():
    g = parse_edge_list("V: c b a d\na b\n")
    assert g.vertices == ["c", "b", "a", "d"]


def test_edge_list_errors():
    with pytest.raises(ParseError, match="строка 2: не указан вес"):
        parse_edge_list("1 2 3\n1 2", weighted=True)
    with pytest.raises(ParseError, match="строка 1: указан вес, но граф невзвешенный"):
        parse_edge_list("1 2 3")
    with pytest.raises(ParseError, match="строка 1: ожидалось ребро"):
        parse_edge_list("1 2 3 4")
    with pytest.raises(ParseError, match="строка 2: ребро ссылается на несуществующую вершину 'x'"):
        parse_edge_list("V: a b\na x")
    with pytest.raises(ParseError, match="пуст"):
        parse_edge_list("# только комментарий\n")
    with pytest.raises(ParseError, match="указана повторно"):
        parse_edge_list("V: a\nV: b")


# ---------------------------------------------------------------------- #
# Матрица смежности
# ---------------------------------------------------------------------- #

def test_adjacency_matrix_with_names():
    g = parse_adjacency_matrix("V: x y z\n0 1 0\n1 0 1\n0 1 0")
    assert g.vertices == ["x", "y", "z"]
    assert g.to_edge_list() == [("x", "y"), ("y", "z")]


def test_adjacency_matrix_weighted_floats():
    g = parse_adjacency_matrix("0 1.5\n1.5 0", weighted=True)
    assert g.to_edge_list() == [(1, 2, 1.5)]


def test_adjacency_matrix_errors():
    with pytest.raises(ParseError, match="строка 2: в строке 2 элементов, а в первой строке матрицы"):
        parse_adjacency_matrix("0 1 0\n1 0\n0 1 0")
    with pytest.raises(ParseError, match="квадратной, а она 2×3"):
        parse_adjacency_matrix("0 1 0\n1 0 1")
    with pytest.raises(GraphError, match="несимметрична"):
        parse_adjacency_matrix("0 1\n0 0")
    with pytest.raises(ParseError, match="строка 1: в строке V: 3 вершин, а матрица 2×2"):
        parse_adjacency_matrix("V: a b c\n0 1\n1 0")
    with pytest.raises(ParseError, match="строка 2: элемент матрицы смежности: 'x' не является числом"):
        parse_adjacency_matrix("0 1\n1 x")
    with pytest.raises(ParseError, match="пуста"):
        parse_adjacency_matrix("")


# ---------------------------------------------------------------------- #
# Список смежности
# ---------------------------------------------------------------------- #

def test_adjacency_list_unweighted():
    g = parse_adjacency_list("1: 2 3\n2: 1\n3: 1\n4:")
    assert g.vertices == [1, 2, 3, 4]
    assert g == Graph.from_edge_list([(1, 2), (1, 3)], vertices=[1, 2, 3, 4])


def test_adjacency_list_weighted_spacing_variants():
    g = parse_adjacency_list("A: B(4), C (2)\nB: C( 5 )\nC:\n", directed=True, weighted=True)
    assert g.to_edge_list() == [("A", "B", 4), ("A", "C", 2), ("B", "C", 5)]


def test_adjacency_list_vertex_named_v_is_not_directive():
    g = parse_adjacency_list("V: W\nW: V")
    assert g.vertices == ["V", "W"]


def test_adjacency_list_errors():
    with pytest.raises(ParseError, match="строка 1: ожидалась строка вида"):
        parse_adjacency_list("1 2 3")
    with pytest.raises(ParseError, match="строка 2: у вершины 1 уже есть строка"):
        parse_adjacency_list("1: 2\n1: 3\n2: 1\n3: 1")
    with pytest.raises(ParseError, match="строка 1: сосед 5 вершины 1 — несуществующая вершина"):
        parse_adjacency_list("1: 5", directed=True)
    with pytest.raises(ParseError, match="не указан вес"):
        parse_adjacency_list("1: 2\n2: 1", weighted=True)
    with pytest.raises(ParseError, match="указан вес, но граф невзвешенный"):
        parse_adjacency_list("1: 2(3)\n2: 1(3)")
    with pytest.raises(GraphError, match="обоих концов"):
        parse_adjacency_list("1: 2\n2:")
    with pytest.raises(ParseError, match="пуст"):
        parse_adjacency_list("\n\n")


# ---------------------------------------------------------------------- #
# Матрица инцидентности
# ---------------------------------------------------------------------- #

def test_incidence_undirected_with_loop():
    g = parse_incidence_matrix("1 0\n1 2")
    assert g.to_edge_list() == [(1, 2), (2, 2)]


def test_incidence_directed_weighted():
    g = parse_incidence_matrix("V: a b c\n-1  0\n 1 -1\n 0  1\nW: 3 4", directed=True, weighted=True)
    assert g.to_edge_list() == [("a", "b", 3), ("b", "c", 4)]


def test_incidence_without_edges_uses_vertex_line():
    g = parse_incidence_matrix("V: a b")
    assert g.vertices == ["a", "b"] and g.edge_count == 0


def test_incidence_errors():
    with pytest.raises(ParseError, match="добавьте строку «W:"):
        parse_incidence_matrix("1\n1", weighted=True)
    with pytest.raises(ParseError, match="строка 3: указана строка весов W:, но граф невзвешенный"):
        parse_incidence_matrix("1\n1\nW: 5")
    with pytest.raises(ParseError, match="строка 3: в строке W: 2 весов, а рёбер \\(столбцов\\) 1"):
        parse_incidence_matrix("1\n1\nW: 5 6", weighted=True)
    with pytest.raises(ParseError, match="в строке V: 3 вершин, а в матрице 2 строк"):
        parse_incidence_matrix("V: a b c\n1\n1")
    with pytest.raises(GraphError, match="столбец e2: ожидалось две единицы"):
        parse_incidence_matrix("1 1\n1 1\n0 1")
    with pytest.raises(GraphError, match="столбец e1: ожидалось одна -1"):
        parse_incidence_matrix("1\n1", directed=True)
    with pytest.raises(ParseError, match="пуста"):
        parse_incidence_matrix("")


# ---------------------------------------------------------------------- #
# Общие функции и файлы примеров
# ---------------------------------------------------------------------- #

def test_parse_graph_accepts_string_format():
    assert parse_graph("1 2", "edges") == parse_graph("1 2", Format.EDGE_LIST)


@pytest.mark.parametrize(
    ("file", "fmt", "directed", "weighted", "vertices", "edges"),
    [
        ("edge_list.txt", Format.EDGE_LIST, False, True, 6, 6),
        ("adjacency_matrix.txt", Format.ADJACENCY_MATRIX, True, False, 5, 9),
        ("adjacency_list.txt", Format.ADJACENCY_LIST, True, True, 6, 7),
        ("incidence_matrix.txt", Format.INCIDENCE_MATRIX, False, False, 4, 6),
    ],
)
def test_examples_load(file, fmt, directed, weighted, vertices, edges):
    g = read_graph(EXAMPLES / file, fmt, directed=directed, weighted=weighted)
    assert (g.vertex_count, g.edge_count) == (vertices, edges)


def test_read_graph_missing_file(tmp_path):
    with pytest.raises(GraphError, match="файл не найден"):
        read_graph(tmp_path / "nope.txt", Format.EDGE_LIST)


def test_read_graph_handles_bom_and_bad_encoding(tmp_path):
    good = tmp_path / "bom.txt"
    good.write_bytes("﻿А Б\n".encode("utf-8"))
    assert read_graph(good, Format.EDGE_LIST).vertices == ["А", "Б"]
    bad = tmp_path / "cp1251.txt"
    bad.write_bytes("А Б\n".encode("cp1251"))
    with pytest.raises(GraphError, match="UTF-8"):
        read_graph(bad, Format.EDGE_LIST)
