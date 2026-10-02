"""Отрисовка: рисунок строится и сохраняется для разных графов и раскладок."""

import matplotlib.pyplot as plt
import networkx as nx
import pytest

from graph import Graph
from samples import GRAPHS
from visualize import LAYOUTS, compute_layout, draw_graph, to_networkx


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


@pytest.mark.parametrize("name", GRAPHS)
def test_draw_every_sample(name, tmp_path):
    path = tmp_path / f"{name}.png"
    draw_graph(GRAPHS[name](), save_path=path, show=False)
    assert path.stat().st_size > 1000


@pytest.mark.parametrize("layout", LAYOUTS)
def test_layouts(layout):
    g = Graph.from_edge_list([(1, 2), (2, 3), (3, 4), (4, 1)])
    pos = compute_layout(g, layout)
    assert set(pos) == {1, 2, 3, 4}
    assert len({tuple(round(c, 6) for c in p) for p in pos.values()}) == 4  # вершины не слиплись


def test_unknown_layout():
    with pytest.raises(ValueError, match="неизвестная раскладка"):
        compute_layout(Graph.from_edge_list([(1, 2)]), "random")


def test_empty_graph_draws():
    fig = draw_graph(Graph(), show=False)
    assert fig.axes


def test_weight_labels_and_title():
    g = Graph.from_edge_list([("a", "b", 4), ("b", "a", 9), ("a", "a", 1)], directed=True, weighted=True)
    fig = draw_graph(g, show=False, title="Тест")
    ax = fig.axes[0]
    texts = {t.get_text() for t in ax.texts}
    assert {"4", "9", "1", "a", "b"} <= texts
    assert ax.get_title() == "Тест"
    assert len(ax.patches) == 3  # по стрелке на каждую дугу, включая петлю


@pytest.mark.parametrize("name", ["$$", "$a$", "a$b", "$5"])
def test_dollar_in_vertex_name_is_drawn_literally(name):
    # без экранирования matplotlib принял бы имя за формулу: "$$" падало, "$a$" рисовалось как "a"
    g = Graph.from_edge_list([(name, "b")])
    fig = draw_graph(g, show=False)
    assert name in {t.get_text().replace("\\$", "$") for t in fig.axes[0].texts}
    plt.close(fig)


def test_to_networkx_keeps_multiedges_and_weights():
    g = Graph.from_edge_list([(1, 2, 5), (1, 2, 6)], weighted=True)
    nxg = to_networkx(g)
    assert isinstance(nxg, nx.MultiGraph) and not nxg.is_directed()
    assert sorted(w for _, _, w in nxg.edges(data="weight")) == [5, 6]
