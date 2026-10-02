"""Построение графа по списку рёбер, матрице смежности, списку смежности
или матрице инцидентности и перевод между этими представлениями.

Запуск без аргументов — интерактивное меню. С аргументом ``--input`` —
пакетный режим (см. ``python main.py --help``).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from formatters import describe, pretty, pretty_all, serialize
from graph import Format, Graph, GraphError
from parsers import parse_graph, read_graph

FORMAT_HELP = {
    Format.EDGE_LIST: (
        "Каждая строка — одно ребро: «u v», во взвешенном графе «u v вес».\n"
        "Необязательная строка «V: a b c» задаёт все вершины (нужна для изолированных).\n"
        "Пример:\n"
        "  A B 4\n"
        "  B C 2\n"
        "  A C 7"
    ),
    Format.ADJACENCY_MATRIX: (
        "n строк по n чисел. 0 — ребра нет; иначе в невзвешенном графе —\n"
        "число рёбер, во взвешенном — вес. Петля — число на диагонали.\n"
        "Необязательная первая строка «V: a b c» — имена вершин (по умолчанию 1..n).\n"
        "Пример:\n"
        "  0 1 1\n"
        "  1 0 1\n"
        "  1 1 0"
    ),
    Format.ADJACENCY_LIST: (
        "Строка на каждую вершину: «u: v1 v2 ...», во взвешенном графе\n"
        "«u: v1(w1) v2(w2)». Вершина без соседей — «u:».\n"
        "В неориентированном графе ребро указывается у обоих концов.\n"
        "Пример:\n"
        "  1: 2 3\n"
        "  2: 1\n"
        "  3: 1"
    ),
    Format.INCIDENCE_MATRIX: (
        "Строки — вершины, столбцы — рёбра.\n"
        "Неориентированный граф: в столбце две 1 (петля — одна 2).\n"
        "Ориентированный: -1 у начала дуги, 1 у конца (петля — одна 2).\n"
        "Взвешенный граф: строка «W: w1 w2 ...» с весами рёбер по столбцам.\n"
        "Необязательная строка «V: a b c» — имена вершин (по умолчанию 1..n).\n"
        "Пример (рёбра 1–2 и 2–3):\n"
        "  1 0\n"
        "  1 1\n"
        "  0 1"
    ),
}

FORMAT_ORDER = list(Format)


# ---------------------------------------------------------------------- #
# Ввод-вывод в консоли
# ---------------------------------------------------------------------- #

def _configure_output() -> None:
    """При выводе в файл или канал не падать на символах вне кодировки консоли."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and not stream.isatty():
            stream.reconfigure(errors="replace")


def read_line(prompt: str) -> str:
    """``input()`` без BOM, который Windows PowerShell дописывает в начало канала."""
    return input(prompt).lstrip("\ufeff")


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = read_line(f"{prompt}{suffix}: ").strip()
    return answer or default


def ask_choice(title: str, options: list[str]) -> int:
    """Номер выбранного пункта (с 0)."""
    print(title)
    for number, option in enumerate(options, start=1):
        print(f"  {number}. {option}")
    while True:
        answer = ask("Ваш выбор")
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return int(answer) - 1
        print(f"  Введите число от 1 до {len(options)}.")


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    hint = "Д/н" if default else "д/Н"
    while True:
        answer = read_line(f"{prompt} ({hint}): ").strip().lower()
        if not answer:
            return default
        if answer in ("д", "да", "y", "yes"):
            return True
        if answer in ("н", "нет", "n", "no"):
            return False
        print("  Ответьте «д» или «н».")


def ask_graph_type() -> tuple[Format, bool, bool]:
    fmt = FORMAT_ORDER[ask_choice("\nФормат ввода:", [f.title for f in FORMAT_ORDER])]
    directed = ask_yes_no("Граф ориентированный?")
    weighted = ask_yes_no("Граф взвешенный?")
    return fmt, directed, weighted


def read_lines_from_keyboard() -> str:
    print("Вводите строки. Пустая строка — конец ввода.")
    lines = []
    while True:
        line = read_line("> ")
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------- #
# Действия меню
# ---------------------------------------------------------------------- #

def action_input_keyboard() -> Graph | None:
    fmt, directed, weighted = ask_graph_type()
    print(f"\n{fmt.title}.\n{FORMAT_HELP[fmt]}\n")
    text = read_lines_from_keyboard()
    return _load(lambda: parse_graph(text, fmt, directed=directed, weighted=weighted))


def action_input_file() -> Graph | None:
    fmt, directed, weighted = ask_graph_type()
    path = ask("Путь к файлу")
    if not path:
        print("Путь не указан.")
        return None
    return _load(lambda: read_graph(path.strip('"'), fmt, directed=directed, weighted=weighted))


def _load(build) -> Graph | None:
    try:
        graph = build()
    except GraphError as exc:
        print(f"\nОшибка: {exc}")
        return None
    print(f"\nГраф построен. {describe(graph)}.")
    return graph


def action_show_one(graph: Graph) -> None:
    fmt = FORMAT_ORDER[ask_choice("\nКакое представление показать?", [f.title for f in FORMAT_ORDER])]
    print("\n" + pretty(graph, fmt))


def action_draw(graph: Graph, save: bool) -> None:
    try:
        from visualize import LAYOUTS, draw_graph
        import matplotlib.pyplot as plt
    except ImportError as exc:
        print(f"Для рисования нужны networkx и matplotlib ({exc.name} не найден).\n"
              f"Установите их: pip install -r requirements.txt")
        return
    layout = ask(f"Раскладка ({', '.join(LAYOUTS)})", "spring")
    if layout not in LAYOUTS:
        print(f"Неизвестная раскладка {layout!r}.")
        return
    if save:
        path = Path(ask("Файл для рисунка", "graph.png").strip('"'))
        if not _confirm_overwrite(path):
            return
        try:
            fig = draw_graph(graph, layout=layout, save_path=path, show=False)
        except OSError as exc:
            print(f"Не удалось сохранить рисунок: {exc}")
            return
        plt.close(fig)
        print(f"Рисунок сохранён: {path.resolve()}")
    else:
        print("Открываю окно с рисунком (закройте его, чтобы вернуться в меню)...")
        fig = draw_graph(graph, layout=layout, show=True)
        plt.close(fig)


def action_save(graph: Graph) -> None:
    fmt = FORMAT_ORDER[ask_choice("\nВ каком представлении сохранить?", [f.title for f in FORMAT_ORDER])]
    path = Path(ask("Имя файла", f"graph_{fmt.value}.txt").strip('"'))
    if not _confirm_overwrite(path):
        return
    try:
        save_graph(graph, fmt, path)
    except GraphError as exc:
        print(f"Ошибка: {exc}")
        return
    except OSError as exc:
        print(f"Не удалось записать файл: {exc}")
        return
    print(f"Сохранено: {path.resolve()}")


def _confirm_overwrite(path: Path) -> bool:
    if path.exists():
        return ask_yes_no(f"Файл {path} существует. Перезаписать?")
    return True


def save_graph(graph: Graph, fmt: Format, path: Path) -> None:
    """Сохраняет граф в формате ввода; в начале — комментарий с типом графа."""
    text = serialize(graph, fmt)
    header = (
        f"# {describe(graph)}\n"
        f"# {fmt.title}. Загрузка: ориентированный — {'да' if graph.directed else 'нет'}, "
        f"взвешенный — {'да' if graph.weighted else 'нет'}\n"
    )
    path.write_text(header + text, encoding="utf-8")


MENU = [
    "Ввести граф с клавиатуры",
    "Загрузить граф из файла",
    "Показать все представления",
    "Показать одно представление",
    "Нарисовать граф",
    "Сохранить представление в файл",
    "Сохранить рисунок в файл (PNG)",
]


def interactive() -> None:
    graph: Graph | None = None
    print("=== Построение графа ===")
    while True:
        status = describe(graph) if graph else "граф ещё не задан"
        print(f"\nТекущий граф: {status}")
        for number, item in enumerate(MENU, start=1):
            print(f"  {number}. {item}")
        print("  0. Выход")
        choice = ask("Ваш выбор")

        if choice == "0":
            print("До свидания!")
            return
        if choice in ("1", "2"):
            new_graph = action_input_keyboard() if choice == "1" else action_input_file()
            if new_graph is not None:
                graph = new_graph
                print("\n" + pretty_all(graph))
            continue
        if choice not in {str(i) for i in range(3, len(MENU) + 1)}:
            print("Нет такого пункта.")
            continue
        if graph is None:
            print("Сначала введите или загрузите граф (пункты 1–2).")
            continue

        if choice == "3":
            print("\n" + pretty_all(graph))
        elif choice == "4":
            action_show_one(graph)
        elif choice == "5":
            action_draw(graph, save=False)
        elif choice == "6":
            action_save(graph)
        elif choice == "7":
            action_draw(graph, save=True)


# ---------------------------------------------------------------------- #
# Пакетный режим
# ---------------------------------------------------------------------- #

def build_arg_parser() -> argparse.ArgumentParser:
    formats = [f.value for f in Format]
    parser = argparse.ArgumentParser(
        description="Построение графа и перевод между представлениями. "
                    "Без аргументов запускается интерактивное меню.",
        epilog="Форматы: edges — список рёбер, adjmatrix — матрица смежности, "
               "adjlist — список смежности, incidence — матрица инцидентности.",
    )
    parser.add_argument("-i", "--input", metavar="ФАЙЛ",
                        help="файл с графом («-» — читать из стандартного ввода)")
    parser.add_argument("-f", "--format", choices=formats, help="формат входного файла")
    parser.add_argument("-d", "--directed", action="store_true", help="ориентированный граф")
    parser.add_argument("-w", "--weighted", action="store_true", help="взвешенный граф")
    parser.add_argument("-s", "--show", choices=["all", "none", *formats], default="all",
                        help="что вывести на экран (по умолчанию all)")
    parser.add_argument("-c", "--convert", choices=formats, metavar="ФОРМАТ",
                        help="в каком формате сохранить граф в --output")
    parser.add_argument("-o", "--output", metavar="ФАЙЛ", help="файл для --convert")
    parser.add_argument("--draw", action="store_true", help="открыть окно с рисунком графа")
    parser.add_argument("--png", metavar="ФАЙЛ", help="сохранить рисунок в файл")
    parser.add_argument("--layout", default="spring",
                        choices=["spring", "circular", "shell", "spectral"],
                        help="раскладка вершин на рисунке")
    return parser


def batch(args: argparse.Namespace) -> int:
    if not args.format:
        print("Ошибка: укажите формат входных данных: --format", file=sys.stderr)
        return 2
    if bool(args.convert) != bool(args.output):
        print("Ошибка: --convert и --output указываются вместе", file=sys.stderr)
        return 2
    try:
        if args.input == "-":
            graph = parse_graph(sys.stdin.read(), args.format,
                                directed=args.directed, weighted=args.weighted)
        else:
            graph = read_graph(args.input, args.format,
                               directed=args.directed, weighted=args.weighted)
        if args.show == "all":
            print(pretty_all(graph))
        elif args.show != "none":
            print(describe(graph) + "\n\n" + pretty(graph, args.show))
        if args.convert:
            save_graph(graph, Format(args.convert), Path(args.output))
            print(f"\nСохранено ({Format(args.convert).title}): {args.output}")
    except GraphError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Ошибка записи файла: {exc}", file=sys.stderr)
        return 1

    if args.draw or args.png:
        try:
            import matplotlib.pyplot as plt
            from visualize import draw_graph
        except ImportError as exc:
            print(f"Ошибка: для рисования нужны networkx и matplotlib ({exc.name} не найден)",
                  file=sys.stderr)
            return 1
        fig = draw_graph(graph, layout=args.layout, save_path=args.png, show=args.draw)
        plt.close(fig)
        if args.png:
            print(f"Рисунок сохранён: {args.png}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _configure_output()
    args = build_arg_parser().parse_args(argv)
    if args.input:
        return batch(args)
    try:
        interactive()
    except (EOFError, KeyboardInterrupt):
        print("\nВыход.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
