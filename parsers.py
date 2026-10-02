"""Разбор текстовых представлений графа (ввод с клавиатуры и из файлов).

Общие правила для всех форматов:
    * ``#`` начинает комментарий до конца строки, пустые строки пропускаются.
    * Элементы разделяются пробелами, запятыми или точками с запятой;
      дробные числа пишутся через точку.
    * Имена вершин, состоящие из цифр, становятся числами (``3`` → ``int``),
      остальные — строками. В имени нельзя использовать пробелы и символы
      ``# : ( ) , ;``, а также называть вершину знаком стрелки
      (``-``, ``->``, ``—`` и т. п.).
    * ``V: a b c`` — необязательная строка с именами вершин (для матриц —
      подписи строк/столбцов, для списка рёбер — порядок вершин и
      изолированные вершины). В матрицах без неё вершины называются 1..n.

Форматы:
    Список рёбер            ``u v`` или ``u v вес``; между вершинами можно
                            писать ``-``, ``->``, ``—`` или ``→``.
    Матрица смежности       n строк по n чисел.
    Список смежности        ``u: v1 v2``, во взвешенном графе ``u: v1(w1) v2(w2)``.
                            Вершина без соседей — ``u:``.
    Матрица инцидентности   n строк по m чисел; во взвешенном графе строка
                            ``W: w1 ... wm`` с весами рёбер (столбцов).
"""

from __future__ import annotations

import math
import re
from pathlib import Path

from graph import Format, Graph, GraphError, Vertex, Weight

_SEPARATORS = re.compile(r"[\s,;]+")
_ARROW_TOKENS = {"-", "--", "->", "—", "–", "→"}
_INT = re.compile(r"[+-]?\d+")
_FORBIDDEN_IN_NAME = set("#:(),;")
_DIRECTIVE = re.compile(r"^\s*([A-Za-z])\s*:(.*)$")


class ParseError(GraphError):
    """Ошибка в тексте представления графа; по возможности с номером строки."""

    def __init__(self, message: str, line: int | None = None) -> None:
        self.line = line
        super().__init__(f"строка {line}: {message}" if line is not None else message)


Line = tuple[int, str]  # (номер строки в исходном тексте, содержимое без комментария)


# ---------------------------------------------------------------------- #
# Вспомогательные функции
# ---------------------------------------------------------------------- #

def _content_lines(text: str) -> list[Line]:
    """Строки без комментариев и пустых строк, с исходными номерами."""
    result = []
    for number, raw in enumerate(text.splitlines(), start=1):
        content = raw.split("#", 1)[0].strip()
        if content:
            result.append((number, content))
    return result


def _tokens(content: str) -> list[str]:
    return [t for t in _SEPARATORS.split(content) if t]


def parse_vertex(token: str, line: int | None = None) -> Vertex:
    """Имя вершины: целое число, если токен из цифр, иначе строка."""
    if not token:
        raise ParseError("пустое имя вершины", line)
    if token in _ARROW_TOKENS:
        # в списке рёбер такой токен считается стрелкой между вершинами
        raise ParseError(f"имя вершины {token!r} совпадает со знаком стрелки", line)
    bad =_FORBIDDEN_IN_NAME.intersection(token)
    if bad:
        raise ParseError(
            f"в имени вершины {token!r} недопустимые символы: {' '.join(sorted(bad))}", line
        )
    return int(token) if _INT.fullmatch(token) else token


def parse_number(token: str, line: int | None = None, what: str = "число") -> Weight:
    """Число из токена: ``int``, если целое, иначе ``float``."""
    if _INT.fullmatch(token):
        return int(token)
    try:
        value = float(token)
    except ValueError:
        raise ParseError(f"{what}: {token!r} не является числом", line) from None
    if not math.isfinite(value):
        raise ParseError(f"{what}: {token!r} — допустимы только конечные числа", line)
    return int(value) if value.is_integer() else value


def _take_directive(lines: list[Line], key: str) -> tuple[list[Line], Line | None]:
    """Убирает из ``lines`` строку вида ``KEY: ...`` и возвращает её содержимое после двоеточия."""
    found: Line | None = None
    rest: list[Line] = []
    for number, content in lines:
        match = _DIRECTIVE.match(content)
        if match and match.group(1).upper() == key:
            if found is not None:
                raise ParseError(f"строка {key}: указана повторно (впервые — в строке {found[0]})", number)
            found = (number, match.group(2))
        else:
            rest.append((number, content))
    return rest, found


def _parse_vertex_names(directive: Line | None) -> list[Vertex] | None:
    if directive is None:
        return None
    number, content = directive
    names = [parse_vertex(t, number) for t in _tokens(content)]
    if not names:
        raise ParseError("в строке V: не указано ни одной вершины", number)
    seen: set[Vertex] = set()
    for name in names:
        if name in seen:
            raise ParseError(f"вершина {name!r} указана в строке V: дважды", number)
        seen.add(name)
    return names


def _parse_matrix(lines: list[Line], what: str) -> list[list[Weight]]:
    """Числовая матрица; все строки должны быть одной длины."""
    matrix: list[list[Weight]] = []
    first_line = None
    for number, content in lines:
        row = [parse_number(t, number, f"элемент {what}") for t in _tokens(content)]
        if matrix and len(row) != len(matrix[0]):
            raise ParseError(
                f"в строке {len(row)} элементов, а в первой строке матрицы "
                f"(строка {first_line}) — {len(matrix[0])}",
                number,
            )
        if not matrix:
            first_line = number
        matrix.append(row)
    return matrix


# ---------------------------------------------------------------------- #
# Разбор форматов
# ---------------------------------------------------------------------- #

def parse_edge_list(text: str, *, directed: bool = False, weighted: bool = False) -> Graph:
    """Разбирает список рёбер: ``u v`` или ``u v вес`` в каждой строке."""
    lines, v_line = _take_directive(_content_lines(text), "V")
    vertices = _parse_vertex_names(v_line)
    if not lines and vertices is None:
        raise ParseError("список рёбер пуст: нет ни рёбер, ни строки V: с вершинами")

    known = set(vertices) if vertices is not None else None
    edges = []
    for number, content in lines:
        tokens = [t for t in _tokens(content) if t not in _ARROW_TOKENS]
        expected = 3 if weighted else 2
        if len(tokens) != expected:
            if weighted and len(tokens) == 2:
                problem = "не указан вес (граф взвешенный)"
            elif not weighted and len(tokens) == 3:
                problem = "указан вес, но граф невзвешенный — выберите взвешенный граф"
            else:
                form = "«u v вес»" if weighted else "«u v»"
                problem = f"ожидалось ребро вида {form}, получено {len(tokens)} элемент(а)"
            raise ParseError(problem, number)
        u, v = parse_vertex(tokens[0], number), parse_vertex(tokens[1], number)
        if known is not None:
            for x in (u, v):
                if x not in known:
                    raise ParseError(
                        f"ребро ссылается на несуществующую вершину {x!r} (её нет в строке V:)",
                        number,
                    )
        edge: tuple = (u, v)
        if weighted:
            edge += (parse_number(tokens[2], number, "вес ребра"),)
        edges.append(edge)

    return Graph.from_edge_list(edges, vertices, directed=directed, weighted=weighted)


def parse_adjacency_matrix(text: str, *, directed: bool = False, weighted: bool = False) -> Graph:
    """Разбирает квадратную матрицу смежности (строка ``V:`` — подписи вершин)."""
    lines, v_line = _take_directive(_content_lines(text), "V")
    vertices = _parse_vertex_names(v_line)
    if not lines:
        raise ParseError("матрица смежности пуста")

    matrix = _parse_matrix(lines, "матрицы смежности")
    n = len(matrix)
    if len(matrix[0]) != n:
        raise ParseError(
            f"матрица смежности должна быть квадратной, а она {n}×{len(matrix[0])} "
            f"({n} строк по {len(matrix[0])} элементов)"
        )
    if vertices is not None and len(vertices) != n:
        raise ParseError(f"в строке V: {len(vertices)} вершин, а матрица {n}×{n}", v_line[0])
    return Graph.from_adjacency_matrix(matrix, vertices, directed=directed, weighted=weighted)


def parse_adjacency_list(text: str, *, directed: bool = False, weighted: bool = False) -> Graph:
    """Разбирает список смежности: ``u: v1 v2`` или ``u: v1(w1) v2(w2)``."""
    lines = _content_lines(text)
    if not lines:
        raise ParseError("список смежности пуст")

    adjacency: dict[Vertex, list] = {}
    defined_at: dict[Vertex, int] = {}
    for number, content in lines:
        if ":" not in content:
            raise ParseError(f"ожидалась строка вида «вершина: соседи», получено {content!r}", number)
        head, rest = content.split(":", 1)
        u = parse_vertex(head.strip(), number)
        if u in adjacency:
            raise ParseError(f"у вершины {u!r} уже есть строка (строка {defined_at[u]})", number)
        # «b (3)» → «b(3)», чтобы вес не отрывался от вершины при разбиении
        rest = re.sub(r"\s*\(\s*", "(", rest)
        rest = re.sub(r"\s*\)", ")", rest)
        neighbors = []
        for token in _tokens(rest):
            match = re.fullmatch(r"([^()]+)(?:\(([^()]*)\))?", token)
            if not match:
                raise ParseError(f"не удалось разобрать соседа {token!r}", number)
            v = parse_vertex(match.group(1), number)
            weight_token = match.group(2)
            if weighted:
                if weight_token is None:
                    raise ParseError(
                        f"у соседа {token!r} не указан вес — пишите {token}(вес)", number
                    )
                neighbors.append((v, parse_number(weight_token, number, f"вес ребра {u!r}–{v!r}")))
            else:
                if weight_token is not None:
                    raise ParseError(
                        f"у соседа {token!r} указан вес, но граф невзвешенный — "
                        f"выберите взвешенный граф",
                        number,
                    )
                neighbors.append(v)
        adjacency[u] = neighbors
        defined_at[u] = number

    for u, neighbors in adjacency.items():
        for item in neighbors:
            v = item[0] if weighted else item
            if v not in adjacency:
                raise ParseError(
                    f"сосед {v!r} вершины {u!r} — несуществующая вершина: "
                    f"добавьте строку «{v}:» (можно с пустым списком)",
                    defined_at[u],
                )
    return Graph.from_adjacency_list(adjacency, directed=directed, weighted=weighted)


def parse_incidence_matrix(text: str, *, directed: bool = False, weighted: bool = False) -> Graph:
    """Разбирает матрицу инцидентности (строки — вершины, столбцы — рёбра)."""
    lines, v_line = _take_directive(_content_lines(text), "V")
    lines, w_line = _take_directive(lines, "W")
    vertices = _parse_vertex_names(v_line)

    if weighted and w_line is None:
        raise ParseError("граф взвешенный: добавьте строку «W: w1 w2 ...» с весами рёбер")
    if not weighted and w_line is not None:
        raise ParseError(
            "указана строка весов W:, но граф невзвешенный — выберите взвешенный граф",
            w_line[0],
        )

    if lines:
        matrix = _parse_matrix(lines, "матрицы инцидентности")
    elif vertices is not None:
        matrix = [[] for _ in vertices]  # граф без рёбер
    else:
        raise ParseError("матрица инцидентности пуста")

    if vertices is not None and len(vertices) != len(matrix):
        raise ParseError(
            f"в строке V: {len(vertices)} вершин, а в матрице {len(matrix)} строк", v_line[0]
        )

    weights = None
    if w_line is not None:
        number, content = w_line
        weights = [parse_number(t, number, "вес ребра") for t in _tokens(content)]
        if len(weights) != len(matrix[0]):
            raise ParseError(
                f"в строке W: {len(weights)} весов, а рёбер (столбцов) {len(matrix[0])}", number
            )
    return Graph.from_incidence_matrix(matrix, vertices, weights, directed=directed)


_PARSERS = {
    Format.EDGE_LIST: parse_edge_list,
    Format.ADJACENCY_MATRIX: parse_adjacency_matrix,
    Format.ADJACENCY_LIST: parse_adjacency_list,
    Format.INCIDENCE_MATRIX: parse_incidence_matrix,
}


def parse_graph(text: str, fmt: Format | str, *, directed: bool = False, weighted: bool = False) -> Graph:
    """Разбирает текст в заданном формате."""
    return _PARSERS[Format(fmt)](text, directed=directed, weighted=weighted)


def read_graph(
    path: str | Path, fmt: Format | str, *, directed: bool = False, weighted: bool = False
) -> Graph:
    """Читает граф из текстового файла (UTF-8, BOM допускается)."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise GraphError(f"файл не найден: {path}") from None
    except UnicodeDecodeError:
        raise GraphError(f"файл {path} не в кодировке UTF-8") from None
    except OSError as exc:
        raise GraphError(f"не удалось прочитать {path}: {exc.strerror}") from None
    return parse_graph(text, fmt, directed=directed, weighted=weighted)
