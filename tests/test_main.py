"""Консольный интерфейс: пакетный режим и интерактивное меню."""

import builtins

import pytest

import main
from conftest import EXAMPLES
from graph import Format
from parsers import read_graph


def run_batch(*args):
    return main.main(list(args))


def test_batch_shows_all(capsys):
    code = run_batch("-i", str(EXAMPLES / "incidence_matrix.txt"), "-f", "incidence")
    out = capsys.readouterr().out
    assert code == 0
    assert "Неориентированный невзвешенный граф: 4 вершины, 6 рёбер" in out
    for fmt in Format:
        assert fmt.title in out


def test_batch_show_one(capsys):
    run_batch("-i", str(EXAMPLES / "adjacency_list.txt"), "-f", "adjlist", "-d", "-w",
              "-s", "adjmatrix")
    out = capsys.readouterr().out
    assert "Матрица смежности" in out and "Матрица инцидентности" not in out


def test_batch_convert_and_reload(tmp_path, capsys):
    out_file = tmp_path / "converted.txt"
    code = run_batch("-i", str(EXAMPLES / "edge_list.txt"), "-f", "edges", "-w",
                     "-s", "none", "-c", "incidence", "-o", str(out_file))
    assert code == 0
    original = read_graph(EXAMPLES / "edge_list.txt", Format.EDGE_LIST, weighted=True)
    assert read_graph(out_file, Format.INCIDENCE_MATRIX, weighted=True) == original
    assert out_file.read_text(encoding="utf-8").startswith("# Неориентированный взвешенный граф")


def test_batch_png(tmp_path):
    png = tmp_path / "g.png"
    assert run_batch("-i", str(EXAMPLES / "adjacency_matrix.txt"), "-f", "adjmatrix", "-d",
                     "-s", "none", "--png", str(png), "--layout", "circular") == 0
    assert png.stat().st_size > 1000


def test_batch_stdin(monkeypatch, capsys):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("1 2\n2 3\n"))
    assert run_batch("-i", "-", "-f", "edges", "-s", "edges") == 0
    assert "1. 1 — 2" in capsys.readouterr().out


def test_batch_errors(capsys, tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_text("0 1\n0 0\n", encoding="utf-8")
    assert run_batch("-i", str(bad), "-f", "adjmatrix") == 1
    assert "несимметрична" in capsys.readouterr().err
    assert run_batch("-i", str(bad)) == 2
    assert run_batch("-i", str(bad), "-f", "adjmatrix", "-d", "-c", "edges") == 2


def feed(monkeypatch, answers):
    """Подменяет input(): возвращает ответы по очереди."""
    it = iter(answers)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(it))


def test_interactive_keyboard_input_and_save(monkeypatch, capsys, tmp_path):
    out_file = tmp_path / "saved.txt"
    feed(monkeypatch, [
        "1",                # ввести с клавиатуры
        "1", "н", "д",      # список рёбер, неориентированный, взвешенный
        "a b 3", "b c 4", "",
        "4", "2",           # показать матрицу смежности
        "6", "3", str(out_file),  # сохранить список смежности
        "0",
    ])
    main.interactive()
    out = capsys.readouterr().out
    assert "Граф построен. Неориентированный взвешенный граф: 3 вершины, 2 ребра." in out
    assert "a │ 0 3 0" in out
    assert out_file.read_text(encoding="utf-8").endswith("a: b(3)\nb: a(3) c(4)\nc: b(4)\n")


def test_interactive_reports_errors_and_requires_graph(monkeypatch, capsys):
    feed(monkeypatch, [
        "3",                        # показать без графа
        "1", "2", "н", "н",         # матрица смежности
        "0 1", "0 0", "",           # несимметричная
        "9",                        # нет такого пункта
        "0",
    ])
    main.interactive()
    out = capsys.readouterr().out
    assert "Сначала введите или загрузите граф" in out
    assert "Ошибка: матрица смежности несимметрична" in out
    assert "Нет такого пункта." in out


def test_interactive_load_file(monkeypatch, capsys):
    feed(monkeypatch, [
        "2", "4", "н", "н", str(EXAMPLES / "incidence_matrix.txt"),
        "0",
    ])
    main.interactive()
    assert "4 вершины, 6 рёбер" in capsys.readouterr().out


def test_interactive_exit_on_eof(monkeypatch, capsys):
    def eof(prompt=""):
        raise EOFError
    monkeypatch.setattr(builtins, "input", eof)
    assert main.main([]) == 0
    assert "Выход." in capsys.readouterr().out


@pytest.mark.parametrize(("answer", "expected"), [("д", True), ("yes", True), ("н", False), ("", False)])
def test_ask_yes_no(monkeypatch, answer, expected):
    feed(monkeypatch, [answer])
    assert main.ask_yes_no("?") is expected
