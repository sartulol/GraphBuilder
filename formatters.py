"""Текстовый вывод графа.

* ``pretty(graph, fmt)`` — представление для экрана: матрицы в виде
  выровненных таблиц с подписями строк и столбцов.
* ``serialize(graph, fmt)`` — текст в формате ввода (см. ``parsers``),
  который можно сохранить в файл и потом загрузить обратно.
"""

from __future__ import annotations

from graph import Format, Graph, GraphError, Vertex, Weight
from parsers import parse_vertex

_FORBIDDEN_IN_NAME = set("#:(),;")


# ---------------------------------------------------------------------- #
# Общие помощники
# ---------------------------------------------------------------------- #

def format_number(value: Weight) -> str:
    """Число без лишнего ``.0``: ``2.0`` → ``2``, ``2.5`` → ``2.5``."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return repr(value) if isinstance(value, float) else str(value)


def vertex_name(v: Vertex) -> str:
    """Имя вершины для записи в текстовом формате.

    Raises:
        GraphError: имя нельзя записать так, чтобы его потом прочитал парсер.
    """
    name = str(v)
    bad = _FORBIDDEN_IN_NAME.intersection(name)
    if not name or bad or any(ch.isspace() for ch in name):
        raise GraphError(
            f"имя вершины {v!r} нельзя записать в текстовом формате: "
            f"в нём пробелы или символы # : ( ) , ;"
        )
    if parse_vertex(name) != v:
        # например, строка "7" прочиталась бы обратно как число 7
        raise GraphError(f"имя вершины {v!r} при чтении превратится в {parse_vertex(name)!r}")
    return name


def plural(n: int, one: str, few: str, many: str) -> str:
    """``plural(5, "вершина", "вершины", "вершин")`` → ``"5 вершин"``."""
    if n % 10 == 1 and n % 100 != 11:
        word = one
    elif 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        word = few
    else:
        word = many
    return f"{n} {word}"


def describe(graph: Graph) -> str:
    """Краткое описание: тип графа, число вершин и рёбер."""
    kind = "Ориентированный" if graph.directed else "Неориентированный"
    weight = "взвешенный" if graph.weighted else "невзвешенный"
    edges = (
        plural(graph.edge_count, "дуга", "дуги", "дуг") if graph.directed
        else plural(graph.edge_count, "ребро", "ребра", "рёбер")
    )
    return f"{kind} {weight} граф: {plural(graph.vertex_count, 'вершина', 'вершины', 'вершин')}, {edges}"


def format_table(
    row_labels: list[str],
    col_labels: list[str],
    rows: list[list[str]],
    extra_rows: list[tuple[str, list[str]]] | None = None,
) -> str:
    """Таблица с подписями строк и столбцов, столбцы выровнены по правому краю.

    ``extra_rows`` выводятся под чертой (например, строка весов).
    """
    extra_rows = extra_rows or []
    all_labels = row_labels + [label for label, _ in extra_rows]
    label_width = max((len(s) for s in all_labels), default=0)
    widths = [len(c) for c in col_labels]
    for cells in rows + [cells for _, cells in extra_rows]:
        for j, cell in enumerate(cells):
            widths[j] = max(widths[j], len(cell))

    def line(label: str, cells: list[str]) -> str:
        body = " ".join(cell.rjust(w) for cell, w in zip(cells, widths))
        return f"{label.rjust(label_width)} │ {body}".rstrip()

    rule_width = sum(widths) + max(len(widths) - 1, 0)
    rule = "─" * (label_width + 1) + "┼" + "─" * (rule_width + 1)
    out = [line("", col_labels), rule]
    out += [line(label, cells) for label, cells in zip(row_labels, rows)]
    if extra_rows:
        out.append(rule)
        out += [line(label, cells) for label, cells in extra_rows]
    return "\n".join(out)


def _edge_text(graph: Graph, u: Vertex, v: Vertex) -> str:
    arrow = "→" if graph.directed else "—"
    return f"{u} {arrow} {v}"


def _wrap_items(items: list[str], width: int = 78) -> str:
    """Элементы через запятую, перенос строки — только между элементами."""
    lines: list[str] = []
    current = ""
    for item in items:
        candidate = f"{current}, {item}" if current else item
        if current and len(candidate) > width:
            lines.append(current + ",")
            current = item
        else:
            current = candidate
    lines.append(current)
    return "\n".join(lines)


def _isolated(graph: Graph) -> list[Vertex]:
    touched = {x for u, v, _ in graph.edges for x in (u, v)}
    return [v for v in graph.vertices if v not in touched]


def _needs_vertex_line(graph: Graph) -> bool:
    """Нужна ли строка ``V:`` в матрицах (имена отличаются от 1..n)."""
    return graph.vertices != list(range(1, graph.vertex_count + 1))


# ---------------------------------------------------------------------- #
# Вывод на экран
# ---------------------------------------------------------------------- #

def pretty_edge_list(graph: Graph) -> str:
    lines = []
    for number, (u, v, w) in enumerate(graph.edges, start=1):
        weight = f"  (вес {format_number(w)})" if graph.weighted else ""
        lines.append(f"{number:>3}. {_edge_text(graph, u, v)}{weight}")
    if not lines:
        lines.append("  (рёбер нет)")
    isolated = _isolated(graph)
    if isolated:
        lines.append("Изолированные вершины: " + ", ".join(map(str, isolated)))
    return "\n".join(lines)


def pretty_adjacency_matrix(graph: Graph) -> str:
    labels = [str(v) for v in graph.vertices]
    rows = [[format_number(x) for x in row] for row in graph.to_adjacency_matrix()]
    note = "строка — начало дуги, столбец — конец" if graph.directed else "матрица симметрична"
    return format_table(labels, labels, rows) + f"\n({note})"


def pretty_adjacency_list(graph: Graph) -> str:
    adjacency = graph.to_adjacency_list()
    width = max((len(str(v)) for v in adjacency), default=0)
    lines = []
    for v, neighbors in adjacency.items():
        if graph.weighted:
            items = [f"{x}({format_number(w)})" for x, w in neighbors]
        else:
            items = [str(x) for x in neighbors]
        separator = " →" if graph.directed else ":"
        lines.append(f"{str(v).rjust(width)}{separator} {', '.join(items) if items else '∅'}")
    return "\n".join(lines)


def pretty_incidence_matrix(graph: Graph) -> str:
    edges = graph.edges
    if not edges:
        return "(рёбер нет — у матрицы инцидентности 0 столбцов)\nВершины: " + ", ".join(
            map(str, graph.vertices)
        )
    labels = [str(v) for v in graph.vertices]
    columns = [f"e{j}" for j in range(1, len(edges) + 1)]
    rows = [[str(x) for x in row] for row in graph.to_incidence_matrix()]
    extra = [("вес", [format_number(w) for w in graph.edge_weights])] if graph.weighted else None
    legend = _wrap_items(
        [f"e{j} = {_edge_text(graph, u, v)}" for j, (u, v, _) in enumerate(edges, start=1)]
    )
    if graph.directed:
        legend += "\n(-1 — начало дуги, 1 — конец, 2 — петля)"
    else:
        legend += "\n(1 — вершина инцидентна ребру, 2 — петля)"
    return format_table(labels, columns, rows, extra) + "\n" + legend


_PRETTY = {
    Format.EDGE_LIST: pretty_edge_list,
    Format.ADJACENCY_MATRIX: pretty_adjacency_matrix,
    Format.ADJACENCY_LIST: pretty_adjacency_list,
    Format.INCIDENCE_MATRIX: pretty_incidence_matrix,
}


def pretty(graph: Graph, fmt: Format | str) -> str:
    """Представление для экрана с заголовком.

    Если граф нельзя записать в этом представлении (например, кратные рёбра во
    взвешенной матрице смежности), вместо таблицы выводится причина.
    """
    fmt = Format(fmt)
    try:
        body = _PRETTY[fmt](graph)
    except GraphError as exc:
        body = f"Невозможно построить: {exc}"
    return f"── {fmt.title} ──\n{body}"


def pretty_all(graph: Graph) -> str:
    """Описание графа и все четыре представления."""
    return "\n\n".join([describe(graph)] + [pretty(graph, fmt) for fmt in Format])


# ---------------------------------------------------------------------- #
# Текст в формате ввода (для сохранения в файл)
# ---------------------------------------------------------------------- #

def _aligned_rows(matrix: list[list[str]]) -> list[str]:
    if not matrix or not matrix[0]:
        return []
    widths = [max(len(row[j]) for row in matrix) for j in range(len(matrix[0]))]
    return [" ".join(cell.rjust(w) for cell, w in zip(row, widths)) for row in matrix]


def serialize_edge_list(graph: Graph) -> str:
    lines = []
    # V: нужна, если есть изолированные вершины или порядок вершин
    # отличается от порядка их появления в рёбрах
    appearance: list[Vertex] = []
    for u, v, _ in graph.edges:
        for x in (u, v):
            if x not in appearance:
                appearance.append(x)
    if appearance != graph.vertices:
        lines.append("V: " + " ".join(vertex_name(v) for v in graph.vertices))
    for u, v, w in graph.edges:
        line = f"{vertex_name(u)} {vertex_name(v)}"
        if graph.weighted:
            line += f" {format_number(w)}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def serialize_adjacency_matrix(graph: Graph) -> str:
    matrix = graph.to_adjacency_matrix()
    lines = []
    if _needs_vertex_line(graph):
        lines.append("V: " + " ".join(vertex_name(v) for v in graph.vertices))
    lines += _aligned_rows([[format_number(x) for x in row] for row in matrix])
    return "\n".join(lines) + "\n"


def serialize_adjacency_list(graph: Graph) -> str:
    lines = []
    for v, neighbors in graph.to_adjacency_list().items():
        if graph.weighted:
            items = [f"{vertex_name(x)}({format_number(w)})" for x, w in neighbors]
        else:
            items = [vertex_name(x) for x in neighbors]
        lines.append(f"{vertex_name(v)}: {' '.join(items)}".rstrip())
    return "\n".join(lines) + "\n"


def serialize_incidence_matrix(graph: Graph) -> str:
    lines = []
    # у графа без рёбер матрица пустая — тогда вершины задаёт только строка V:
    if _needs_vertex_line(graph) or graph.edge_count == 0:
        lines.append("V: " + " ".join(vertex_name(v) for v in graph.vertices))
    lines += _aligned_rows([[str(x) for x in row] for row in graph.to_incidence_matrix()])
    if graph.weighted:
        lines.append("W: " + " ".join(format_number(w) for w in graph.edge_weights))
    return "\n".join(lines) + "\n"


_SERIALIZERS = {
    Format.EDGE_LIST: serialize_edge_list,
    Format.ADJACENCY_MATRIX: serialize_adjacency_matrix,
    Format.ADJACENCY_LIST: serialize_adjacency_list,
    Format.INCIDENCE_MATRIX: serialize_incidence_matrix,
}


def serialize(graph: Graph, fmt: Format | str) -> str:
    """Текст графа в формате ввода; его можно прочитать ``parsers.parse_graph``."""
    return _SERIALIZERS[Format(fmt)](graph)
