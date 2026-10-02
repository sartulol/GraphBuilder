"""Модель графа и преобразования между четырьмя представлениями.

Граф хранится в одном внутреннем виде: упорядоченный список вершин и список
рёбер ``(u, v, w)``. Из него строятся список рёбер, матрица смежности,
список смежности и матрица инцидентности, и в него же разбираются все
четыре представления.

Соглашения:
    * Вершины — любые хешируемые значения (на практике ``int`` или ``str``).
      Порядок вершин сохраняется и задаёт порядок строк/столбцов матриц.
    * У невзвешенного графа вес каждого ребра равен 1.
    * Кратные рёбра и петли допускаются. Во взвешенной матрице смежности
      кратные рёбра непредставимы — для них выбрасывается ``GraphError``.
    * Матрица смежности невзвешенного графа хранит число рёбер между
      вершинами; петля неориентированного графа даёт 1 на диагонали.
    * Матрица инцидентности: в неориентированном графе у ребра две единицы,
      у петли — одна двойка; в ориентированном у дуги -1 в начале и 1 в
      конце, у петли — одна двойка. Веса хранятся отдельно (``edge_weights``).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Hashable, Iterable, Mapping, Sequence
from enum import Enum
from numbers import Real
from typing import Any

Vertex = Hashable
Weight = int | float
Edge = tuple[Vertex, Vertex, Weight]


class GraphError(ValueError):
    """Некорректные данные графа или невозможное преобразование."""


class Format(str, Enum):
    """Четыре поддерживаемых представления графа."""

    EDGE_LIST = "edges"
    ADJACENCY_MATRIX = "adjmatrix"
    ADJACENCY_LIST = "adjlist"
    INCIDENCE_MATRIX = "incidence"

    @property
    def title(self) -> str:
        return _FORMAT_TITLES[self]


_FORMAT_TITLES = {
    Format.EDGE_LIST: "Список рёбер",
    Format.ADJACENCY_MATRIX: "Матрица смежности",
    Format.ADJACENCY_LIST: "Список смежности",
    Format.INCIDENCE_MATRIX: "Матрица инцидентности",
}


def _check_number(value: Any, what: str) -> Weight:
    """Проверяет, что ``value`` — конечное число, и возвращает его."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise GraphError(f"{what}: ожидалось число, получено {value!r}")
    if isinstance(value, float) and not math.isfinite(value):
        raise GraphError(f"{what}: число должно быть конечным, получено {value!r}")
    return value


def _check_unique(vertices: Sequence[Vertex]) -> None:
    seen: set[Vertex] = set()
    for v in vertices:
        if v in seen:
            raise GraphError(f"вершина {v!r} указана дважды")
        seen.add(v)


class Graph:
    """Граф (ориентированный или нет, взвешенный или нет) с кратными рёбрами и петлями."""

    def __init__(self, directed: bool = False, weighted: bool = False) -> None:
        self.directed = directed
        self.weighted = weighted
        self._vertices: list[Vertex] = []
        self._index: dict[Vertex, int] = {}
        self._edges: list[Edge] = []

    # ------------------------------------------------------------------ #
    # Базовые операции
    # ------------------------------------------------------------------ #

    @property
    def vertices(self) -> list[Vertex]:
        """Вершины в порядке добавления (копия)."""
        return list(self._vertices)

    @property
    def edges(self) -> list[Edge]:
        """Рёбра ``(u, v, w)`` в порядке добавления (копия)."""
        return list(self._edges)

    @property
    def edge_weights(self) -> list[Weight]:
        """Веса рёбер в порядке столбцов матрицы инцидентности."""
        return [w for _, _, w in self._edges]

    @property
    def vertex_count(self) -> int:
        return len(self._vertices)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def has_vertex(self, v: Vertex) -> bool:
        return v in self._index

    def index_of(self, v: Vertex) -> int:
        """Номер вершины (строки/столбца матрицы), начиная с 0."""
        try:
            return self._index[v]
        except KeyError:
            raise GraphError(f"вершины {v!r} нет в графе") from None

    def add_vertex(self, v: Vertex) -> None:
        """Добавляет вершину; повторное добавление ничего не делает."""
        try:
            hash(v)
        except TypeError:
            raise GraphError(f"имя вершины должно быть хешируемым, получено {v!r}") from None
        if v not in self._index:
            self._index[v] = len(self._vertices)
            self._vertices.append(v)

    def add_edge(self, u: Vertex, v: Vertex, weight: Weight | None = None) -> None:
        """Добавляет ребро (дугу ``u → v``). Отсутствующие вершины создаются.

        У взвешенного графа вес обязателен, у невзвешенного — запрещён.
        """
        if self.weighted:
            if weight is None:
                raise GraphError(f"у ребра ({u!r}, {v!r}) взвешенного графа не указан вес")
            weight = _check_number(weight, f"вес ребра ({u!r}, {v!r})")
        else:
            if weight is not None:
                raise GraphError(
                    f"у ребра ({u!r}, {v!r}) указан вес {weight!r}, но граф невзвешенный"
                )
            weight = 1
        self.add_vertex(u)
        self.add_vertex(v)
        self._edges.append((u, v, weight))

    def neighbors(self, v: Vertex) -> list[Vertex]:
        """Соседи вершины (для орграфа — концы исходящих дуг), с повторами для кратных рёбер."""
        self.index_of(v)  # проверка, что вершина есть
        items = self.to_adjacency_list()[v]
        return [x for x, _ in items] if self.weighted else items

    def has_parallel_edges(self) -> bool:
        """Есть ли в графе кратные рёбра (или кратные петли)."""
        counts = Counter(self._edge_key(u, v) for u, v, _ in self._edges)
        return any(c > 1 for c in counts.values())

    def _edge_key(self, u: Vertex, v: Vertex) -> Any:
        return (u, v) if self.directed else frozenset((u, v))

    # ------------------------------------------------------------------ #
    # Сравнение и вывод
    # ------------------------------------------------------------------ #

    def __eq__(self, other: object) -> bool:
        """Графы равны, если совпадают тип, множества вершин и мультимножества рёбер.

        Порядок вершин и рёбер не учитывается; у неориентированного графа
        ребро ``(u, v)`` равно ребру ``(v, u)``.
        """
        if not isinstance(other, Graph):
            return NotImplemented
        return (
            self.directed == other.directed
            and self.weighted == other.weighted
            and set(self._vertices) == set(other._vertices)
            and self._edge_multiset() == other._edge_multiset()
        )

    __hash__ = None  # type: ignore[assignment]  # граф изменяемый

    def _edge_multiset(self) -> Counter:
        return Counter((self._edge_key(u, v), w) for u, v, w in self._edges)

    def __repr__(self) -> str:
        kind = "ориентированный" if self.directed else "неориентированный"
        weight = "взвешенный" if self.weighted else "невзвешенный"
        return (
            f"Graph({kind}, {weight}, вершин: {self.vertex_count}, "
            f"рёбер: {self.edge_count})"
        )

    # ------------------------------------------------------------------ #
    # Построение из представлений
    # ------------------------------------------------------------------ #

    @classmethod
    def from_edge_list(
        cls,
        edges: Iterable[Sequence[Any]],
        vertices: Sequence[Vertex] | None = None,
        *,
        directed: bool = False,
        weighted: bool = False,
    ) -> Graph:
        """Строит граф по списку рёбер ``(u, v)`` или ``(u, v, w)``.

        Если ``vertices`` не задан, вершины берутся из рёбер в порядке
        появления. Если задан — рёбра могут ссылаться только на эти вершины
        (так же можно задать изолированные вершины и их порядок).
        """
        g = cls(directed=directed, weighted=weighted)
        if vertices is not None:
            _check_unique(vertices)
            for v in vertices:
                g.add_vertex(v)

        for num, edge in enumerate(edges, start=1):
            edge = tuple(edge)
            if weighted:
                if len(edge) != 3:
                    raise GraphError(
                        f"ребро №{num} {edge!r}: во взвешенном графе ребро задаётся как (u, v, вес)"
                    )
            elif len(edge) != 2:
                hint = " (вес указан, но граф невзвешенный)" if len(edge) == 3 else ""
                raise GraphError(
                    f"ребро №{num} {edge!r}: ожидалась пара (u, v){hint}"
                )
            u, v = edge[0], edge[1]
            if vertices is not None:
                for x in (u, v):
                    if not g.has_vertex(x):
                        raise GraphError(
                            f"ребро №{num} ({u!r}, {v!r}) ссылается на несуществующую вершину {x!r}"
                        )
            g.add_edge(u, v, edge[2] if weighted else None)
        return g

    @classmethod
    def from_adjacency_matrix(
        cls,
        matrix: Sequence[Sequence[Any]],
        vertices: Sequence[Vertex] | None = None,
        *,
        directed: bool = False,
        weighted: bool = False,
    ) -> Graph:
        """Строит граф по квадратной матрице смежности.

        Невзвешенный граф: элемент — неотрицательное целое число рёбер между
        вершинами. Взвешенный: 0 — ребра нет, иначе элемент — вес ребра.
        Вершины по умолчанию называются 1..n.
        """
        n = len(matrix)
        for i, row in enumerate(matrix):
            if len(row) != n:
                raise GraphError(
                    f"матрица смежности должна быть квадратной: в ней {n} строк, "
                    f"а в строке {i + 1} — {len(row)} элементов"
                )
        vertices = cls._resolve_vertices(vertices, n, "строк матрицы смежности")

        for i in range(n):
            for j in range(n):
                where = f"элемент [{vertices[i]!r}][{vertices[j]!r}]"
                value = _check_number(matrix[i][j], where)
                if not weighted and (value < 0 or value != int(value)):
                    raise GraphError(
                        f"{where} = {value!r}: в невзвешенном графе элементы матрицы — "
                        f"неотрицательные целые (число рёбер). Для весов выберите "
                        f"взвешенный граф"
                    )

        if not directed:
            for i in range(n):
                for j in range(i + 1, n):
                    if matrix[i][j] != matrix[j][i]:
                        raise GraphError(
                            f"матрица смежности несимметрична: "
                            f"[{vertices[i]!r}][{vertices[j]!r}] = {matrix[i][j]!r}, "
                            f"а [{vertices[j]!r}][{vertices[i]!r}] = {matrix[j][i]!r}. "
                            f"У неориентированного графа она должна быть симметричной"
                        )

        g = cls(directed=directed, weighted=weighted)
        for v in vertices:
            g.add_vertex(v)
        for i in range(n):
            # у неориентированного графа матрица симметрична — берём верхний треугольник
            for j in range(0 if directed else i, n):
                value = matrix[i][j]
                if value == 0:
                    continue
                if weighted:
                    g.add_edge(vertices[i], vertices[j], value)
                else:
                    for _ in range(int(value)):
                        g.add_edge(vertices[i], vertices[j])
        return g

    @classmethod
    def from_adjacency_list(
        cls,
        adjacency: Mapping[Vertex, Iterable[Any]],
        *,
        directed: bool = False,
        weighted: bool = False,
    ) -> Graph:
        """Строит граф по списку смежности ``{вершина: [соседи]}``.

        Во взвешенном графе сосед задаётся парой ``(вершина, вес)``.
        У неориентированного графа каждое ребро должно быть указано у обоих
        концов (петля — один раз), иначе выбрасывается ``GraphError``.
        """
        vertices = list(adjacency)
        index = {v: i for i, v in enumerate(vertices)}
        entries: list[tuple[Vertex, Vertex, Weight | None]] = []

        for u in vertices:
            for item in adjacency[u]:
                if weighted:
                    if not isinstance(item, (tuple, list)) or len(item) != 2:
                        raise GraphError(
                            f"вершина {u!r}: во взвешенном графе сосед задаётся как "
                            f"(вершина, вес), получено {item!r}"
                        )
                    v, w = item
                    w = _check_number(w, f"вес ребра ({u!r}, {v!r})")
                else:
                    v, w = item, None
                if v not in index:
                    raise GraphError(
                        f"в списке вершины {u!r} указан сосед {v!r}, "
                        f"но такой вершины нет (у неё нет своей строки)"
                    )
                entries.append((u, v, w))

        g = cls(directed=directed, weighted=weighted)
        for v in vertices:
            g.add_vertex(v)

        if directed:
            for u, v, w in entries:
                g.add_edge(u, v, w)
            return g

        # Неориентированный граф: ребро u–v записано и у u, и у v (с тем же
        # весом и столько же раз). Проверяем это, затем берём каждое ребро
        # один раз — из списка конца с меньшим номером.
        counts = Counter(entries)
        for (u, v, w), count in counts.items():
            if u != v and counts[(v, u, w)] != count:
                w_text = "" if w is None else f" с весом {w!r}"
                raise GraphError(
                    f"ребро {u!r}–{v!r}{w_text} указано в списке вершины {u!r} "
                    f"{count} раз(а), а в списке вершины {v!r} — {counts[(v, u, w)]}. "
                    f"В неориентированном графе ребро должно быть в списках обоих концов"
                )
        for u, v, w in entries:
            if index[u] <= index[v]:
                g.add_edge(u, v, w)
        return g

    @classmethod
    def from_incidence_matrix(
        cls,
        matrix: Sequence[Sequence[Any]],
        vertices: Sequence[Vertex] | None = None,
        weights: Sequence[Any] | None = None,
        *,
        directed: bool = False,
    ) -> Graph:
        """Строит граф по матрице инцидентности (строки — вершины, столбцы — рёбра).

        Граф считается взвешенным, если передан ``weights`` — по весу на столбец.
        """
        n = len(matrix)
        m = len(matrix[0]) if n else 0
        for i, row in enumerate(matrix):
            if len(row) != m:
                raise GraphError(
                    f"в строках матрицы инцидентности разное число столбцов: "
                    f"в строке 1 — {m}, в строке {i + 1} — {len(row)}"
                )
        vertices = cls._resolve_vertices(vertices, n, "строк матрицы инцидентности")
        if weights is not None:
            weights = list(weights)
            if len(weights) != m:
                raise GraphError(
                    f"весов {len(weights)}, а рёбер (столбцов) в матрице инцидентности {m}"
                )

        g = cls(directed=directed, weighted=weights is not None)
        for v in vertices:
            g.add_vertex(v)

        allowed = {0, 1, -1, 2} if directed else {0, 1, 2}
        for j in range(m):
            column = f"столбец e{j + 1}"
            nonzero: list[tuple[int, Weight]] = []
            for i in range(n):
                value = _check_number(matrix[i][j], f"{column}, строка {vertices[i]!r}")
                if value not in allowed:
                    allowed_text = ", ".join(str(a) for a in sorted(allowed))
                    raise GraphError(
                        f"{column}, строка {vertices[i]!r}: значение {value!r} недопустимо, "
                        f"разрешены только {allowed_text}"
                    )
                if value != 0:
                    nonzero.append((i, value))

            values = sorted(val for _, val in nonzero)
            if values == [2]:
                u = v = vertices[nonzero[0][0]]
            elif not directed and values == [1, 1]:
                u, v = vertices[nonzero[0][0]], vertices[nonzero[1][0]]
            elif directed and values == [-1, 1]:
                u = next(vertices[i] for i, val in nonzero if val == -1)
                v = next(vertices[i] for i, val in nonzero if val == 1)
            else:
                expected = (
                    "одна -1 (начало дуги) и одна 1 (конец)" if directed
                    else "две единицы"
                )
                found = ", ".join(f"{vertices[i]!r}: {val}" for i, val in nonzero) or "только нули"
                raise GraphError(
                    f"{column}: ожидалось {expected} или одна двойка (петля), "
                    f"найдено — {found}"
                )
            g.add_edge(u, v, weights[j] if weights is not None else None)
        return g

    @staticmethod
    def _resolve_vertices(
        vertices: Sequence[Vertex] | None, n: int, what: str
    ) -> list[Vertex]:
        if vertices is None:
            return list(range(1, n + 1))
        vertices = list(vertices)
        if len(vertices) != n:
            raise GraphError(f"задано {len(vertices)} имён вершин, а {what} — {n}")
        _check_unique(vertices)
        return vertices

    # ------------------------------------------------------------------ #
    # Преобразование в представления
    # ------------------------------------------------------------------ #

    def to_edge_list(self) -> list[tuple]:
        """Список рёбер: ``(u, v)`` или ``(u, v, w)`` для взвешенного графа.

        Изолированные вершины в нём не видны — их даёт ``vertices``.
        """
        if self.weighted:
            return list(self._edges)
        return [(u, v) for u, v, _ in self._edges]

    def to_adjacency_matrix(self) -> list[list[Weight]]:
        """Матрица смежности n×n в порядке ``vertices``.

        Raises:
            GraphError: во взвешенном графе есть кратные рёбра или ребро
                с весом 0 — матрица смежности их не различает.
        """
        n = self.vertex_count
        matrix: list[list[Weight]] = [[0] * n for _ in range(n)]
        for u, v, w in self._edges:
            i, j = self._index[u], self._index[v]
            if self.weighted:
                if w == 0:
                    raise GraphError(
                        f"ребро ({u!r}, {v!r}) имеет вес 0: во взвешенной матрице "
                        f"смежности 0 означает отсутствие ребра"
                    )
                if matrix[i][j] != 0:
                    raise GraphError(
                        f"между {u!r} и {v!r} несколько рёбер: взвешенная матрица "
                        f"смежности не может хранить кратные рёбра"
                    )
                matrix[i][j] = w
                if not self.directed:
                    matrix[j][i] = w
            else:
                matrix[i][j] += 1
                if not self.directed and i != j:
                    matrix[j][i] += 1
        return matrix

    def to_adjacency_list(self) -> dict[Vertex, list[Any]]:
        """Список смежности ``{вершина: [соседи]}`` в порядке ``vertices``.

        Во взвешенном графе сосед — пара ``(вершина, вес)``. У неориентированного
        графа ребро попадает в списки обоих концов, петля — один раз.
        """
        adjacency: dict[Vertex, list[Any]] = {v: [] for v in self._vertices}
        for u, v, w in self._edges:
            adjacency[u].append((v, w) if self.weighted else v)
            if not self.directed and u != v:
                adjacency[v].append((u, w) if self.weighted else u)
        return adjacency

    def to_incidence_matrix(self) -> list[list[int]]:
        """Матрица инцидентности n×m: строки — ``vertices``, столбцы — ``edges``.

        Веса столбцов — ``edge_weights``.
        """
        matrix = [[0] * self.edge_count for _ in range(self.vertex_count)]
        for j, (u, v, _) in enumerate(self._edges):
            i_u, i_v = self._index[u], self._index[v]
            if i_u == i_v:
                matrix[i_u][j] = 2
            elif self.directed:
                matrix[i_u][j] = -1
                matrix[i_v][j] = 1
            else:
                matrix[i_u][j] = 1
                matrix[i_v][j] = 1
        return matrix
