import os
import pathlib
import random
import re
import signal
import subprocess
import sys
import tempfile
from inspect import currentframe, getframeinfo
from itertools import count
from typing import Literal

from PySide6.QtCore import QThreadPool, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from autoanki.editor_interface import BufferRead, BufferWrite
from autoanki.notes import Basic, Basic_And_Reversed, Cloze

Note = type[Basic] | type[Basic_And_Reversed] | type[Cloze]
NoteObj = Basic | Cloze


class NoteGenerator(QWidget):
    def __init__(self) -> None:
        super().__init__()
        try:
            self.subject: str = f"{sys.argv[1]}-"
        except IndexError:
            self.subject = ""

        self.note_width: int = 500
        self.note_height = 300

        self.threadpool = QThreadPool()
        self.timer = QTimer()
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.spawn)
        self.timer.start()

        self.temp_file = tempfile.NamedTemporaryFile(suffix=".tex")
        self.temp_file_name: str = self.temp_file.name
        self.buffer = "\n"
        self.last_buffer = ""
        self.displaying: Literal["all"] | int = "all"

        self.layout: QVBoxLayout = QVBoxLayout()
        self.margins: list[int] = [10, 10, 10, 10]  # left, top, right, bottom
        self.layout.setContentsMargins(
            self.margins[0], self.margins[1], self.margins[2], self.margins[3]
        )
        self.spacing = 10
        self.layout.setSpacing(self.spacing)

        self.web_view_grid = QGridLayout()
        self.web_views: list[QWebEngineView] = []

        self.notes: list[NoteObj] = []
        self.output_file = "autoanki.md"
        self.temp_output_file = tempfile.TemporaryFile()

        self.layout.addLayout(self.web_view_grid)

        self.tabButtons = QHBoxLayout()
        all_button = QPushButton("All")
        all_button.pressed.connect(lambda: self.switch_web_view("all"))
        self.buttons: list[QPushButton] = [all_button]
        self.tabButtons.addWidget(all_button)

        self.layout.addLayout(self.tabButtons)

        self.setLayout(self.layout)

        self.editor = subprocess.Popen([
            "kitty",
            "nvim",
            "--listen",
            "/tmp/nvim.sock",
            self.temp_file_name,
        ])

    def update_web_view(self, buffer: str) -> None:
        pass

    def spawn(self) -> None:
        worker = BufferRead(self.temp_file)
        worker.signals.reload.connect(self.update_web_view)
        self.threadpool.start(worker.buffer_read(self.buffer))

    def set_number_of_notes(self, num: list[tuple[int, Note]]) -> None:
        self.notes: list[Note] = []
        self.web_views: list[QWebEngineView] = []
        self.add_notes(num)

    def add_notes(self, to_add: list[tuple[int, Note]]) -> None:
        for note_set in to_add:
            for _ in range(note_set[0]):
                self.web_views.append(QWebEngineView())
                self.notes.append(note_set[1]())

    def switch_web_view(self, notes: str | int) -> None:
        self.displaying: int = notes if isinstance(notes, int) else -1
        if notes == "all":
            notes_to_show: list[NoteObj] = self.notes
            self.threadpool.start(BufferWrite().buffer_write(self.buffer))
            notes_len: int = len(notes_to_show)
        elif isinstance(notes, int):
            notes_len = 1
            notes_to_show: list[NoteObj | None] = [None] * len(self.notes)
            notes_to_show[notes] = self.notes[notes]
            self.threadpool.start(BufferWrite().buffer_write(str(self.notes[notes])))

        # note_layouts[i] holds the layout for i many notes
        # each layout has the form [x, y]*however many notes
        note_layouts: list[list[list[int]]] = [
            [[0, 0]],
            [[0, 0]],
            [[0, 0], [0, 1]],
            [[0, 0], [0, 1], [0, 2]],
            [[0, 0], [0, 1], [1, 0], [1, 1]],
            [[0, 0, 1, 2], [0, 2, 1, 2], [0, 4, 1, 2], [1, 1, 1, 2], [1, 3, 1, 2]],
        ]
        grid_xy: list[list[int]] = [[], [1, 1], [2, 1], [3, 1], [2, 2], [3, 2]]

        for vw in self.web_views:
            self.web_view_grid.removeWidget(vw)
            vw.hide()

        for i, note in enumerate(notes_to_show):
            if note is not None:
                web_view = self.web_views[i]
                web_view.setHtml(note.html())
                x: int = note_layouts[len(notes_to_show)][i][0]
                y: int = note_layouts[len(notes_to_show)][i][1]

                web_view.setFixedSize(self.note_width, self.note_height)
                web_view.resize(self.note_width, self.note_height)
                web_view.show()
                if len(note_layouts[len(notes_to_show)][i]) > 2:
                    x2: int = note_layouts[len(notes_to_show)][i][2]
                    y2: int = note_layouts[len(notes_to_show)][i][3]
                    self.web_view_grid.addWidget(web_view, x, y, x2, y2)
                else:
                    self.web_view_grid.addWidget(web_view, x, y)

        window_width = (
            (grid_xy[notes_len][0] * (self.note_width + self.spacing))
            - self.spacing
            + self.margins[0]
            + self.margins[2]
        )
        window_height = (
            (grid_xy[notes_len][1] * (self.note_height + self.spacing))
            + 50
            + self.margins[1]
            + self.margins[2]
        )
        self.resize(window_width, window_height)

    @staticmethod
    def capitalise(text: str) -> str:
        for i in range(len(text)):
            if text[i].isalpha():
                return f"{text[:i]}{text[i].upper()}{text[i + 1 :]}"

        return text

    @staticmethod
    def split_equations(eqn_string: str, subject_symbol: str) -> list[str]:
        formulae = []
        eqn_string = eqn_string.replace("\\(", "").replace("\\)", "")
        subject_symbol = subject_symbol.replace("\\(", "").replace("\\)", "")
        for segment in eqn_string.split("="):
            if f"{segment.strip()}" == subject_symbol:
                continue

            formulae.append(f"{subject_symbol}={segment}")

        return formulae

    def closeEvent(self, _: QCloseEvent) -> None:
        self.threadpool.start(BufferWrite().buffer_write(""))
        self.temp_output_file.seek(0)
        notes = self.temp_output_file.read().decode("utf-8")
        if not notes.replace("\n", "").strip():
            with pathlib.Path(self.output_file).open("a") as f:
                f.write(notes)

        os.kill(self.editor.pid, signal.SIGINT)


class SingleBasic(NoteGenerator):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Basic Note"
        self.setWindowTitle(self.name)
        if not self.output_file:
            self.output_file = "basic-notes.md"
        self.template = ""

        self.set_number_of_notes([(1, Basic)])
        self.switch_web_view("all")
        self.notes: list[Basic]

    def update_web_view(self, buffer: str) -> None:
        if buffer == self.buffer:
            return

        if self.displaying == -1:
            self.buffer = buffer

        buffer = buffer.replace("<mathjax>", "").replace("</mathjax>", "")
        bl = buffer.split("\n")
        if len(bl) >= 2:
            front = bl[0]
            back = bl[1]
            if self.notes[0].front != front or self.notes[0].back != back:
                self.notes[0].front = front
                self.notes[0].back = back
                self.web_views[0].setHtml(self.notes[0].html())

            self.temp_output_file.seek(0)
            for note in self.notes:
                self.temp_output_file.write(str(note).encode("utf-8"))


class MathsIdentity(NoteGenerator):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Maths Identity"
        self.setWindowTitle(self.name)
        if not self.output_file:
            self.output_file = "maths-identities.md"
        self.template = "anki-maths-identity"
        self.min_redraw_lines = 5
        self.notes: list[Basic]

        self.set_number_of_notes([(2, Basic)])
        self.switch_web_view("all")

        text_button = QPushButton("Text card")
        text_button.pressed.connect(lambda: self.switch_web_view(0))
        self.tabButtons.addWidget(text_button)

        tex_button = QPushButton("Tex card")
        tex_button.pressed.connect(lambda: self.switch_web_view(1))
        self.tabButtons.addWidget(tex_button)

    def update_web_view(self, buffer: str) -> None:
        if buffer == self.buffer:
            return

        if self.displaying == -1:
            self.buffer = buffer

        bl = buffer.split("\n")
        if len(bl) > 1:
            note_0 = self.notes[0]
            note_0_front = f"{bl[0]} {bl[1]} {bl[2]}"
            note_01_back = bl[3]
            if note_0.front != note_0_front or note_0.back != note_01_back:
                note_0.front = note_0_front
                note_0.back = note_01_back
                self.web_views[0].setHtml(note_0.html())
            note_1 = self.notes[1]
            note_1_front = f"{bl[4]} {bl[1]} {bl[5]}"
            if note_1.front != note_1_front or note_1.back != note_01_back:
                note_1.front = note_1_front
                note_1.back = note_01_back
                self.web_views[1].setHtml(note_1.html())

            self.temp_output_file.seek(0)
            for note in self.notes:
                self.temp_output_file.write(str(note).encode("utf-8"))


class Definition(NoteGenerator):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Definition"
        self.setWindowTitle(self.name)
        self.output_file = f"{self.subject}definitions.md"
        self.template = "anki-definition"

        self.base_notes: list[tuple[int, Note]] = [(2, Cloze), (1, Basic_And_Reversed)]
        self.set_number_of_notes(self.base_notes)
        self.switch_web_view("all")

        definition_cloze_button = QPushButton("Definition Cloze")
        definition_cloze_button.pressed.connect(lambda: self.switch_web_view(0))
        self.buttons.append(definition_cloze_button)
        self.tabButtons.addWidget(definition_cloze_button)

        formula_cloze_button = QPushButton("Formula Cloze")
        formula_cloze_button.pressed.connect(lambda: self.switch_web_view(1))
        self.buttons.append(formula_cloze_button)
        self.tabButtons.addWidget(formula_cloze_button)

        formula_basic_and_reversed_button = QPushButton("Formula BnR")
        formula_basic_and_reversed_button.pressed.connect(
            lambda: self.switch_web_view(2)
        )
        self.buttons.append(formula_basic_and_reversed_button)
        self.tabButtons.addWidget(formula_basic_and_reversed_button)

    @staticmethod
    def update_cloze(bl: list[str], note: Cloze) -> None:
        for i in range(len(bl[1:])):
            if bl[i].replace(" ", "") == "##Text":
                for line in bl[i + 1 :]:
                    if line.replace(" ", "") == "##BackExtra":
                        break
                    note.text += f"\n{line.strip()}"
            elif bl[i].replace(" ", "") == "##BackExtra":
                for line in bl[i + 1 :]:
                    note.back_extra += f"\n{line.strip()}"

    @staticmethod
    def update_basic(bl: list[str], card: Basic) -> None:
        card.front = ""
        card.back = ""
        for i in range(len(bl[1:])):
            if bl[i].replace(" ", "") == "##Front":
                for line in bl[i + 1 :]:
                    if line.replace(" ", "") == "##Back":
                        break
                    card.front += f"\n{line.strip()}"
            elif bl[i].replace(" ", "") == "##Back":
                for line in bl[i + 1 :]:
                    card.back += f"\n{line.strip()}"

    def update_single_card(self, bl: list[str], note: NoteObj) -> None:
        if isinstance(note, Cloze):
            self.update_cloze(bl, note)
        elif isinstance(note, Basic):
            self.update_basic(bl, note)

    def update_web_view(self, buffer: str):
        if buffer == self.buffer + "\n" or buffer[:-2] == self.last_buffer + "\n":
            return

        self.last_buffer = buffer

        if self.displaying == -1:
            self.buffer = buffer

        print(f"{getframeinfo(currentframe()).lineno} {self.displaying=}")

        bl = buffer.split("\n")
        if self.displaying >= 0:
            this_note = self.notes[self.displaying]
            self.update_single_card(bl, this_note)
            self.web_views[self.displaying].setHtml(this_note.html())

            self.temp_output_file.seek(0)
            for note in self.notes:
                self.temp_output_file.write(str(note).encode("utf-8"))

            return

        subject = ""
        context = ""
        symbol = ""
        definition = ""
        equation_string = ""
        units = ""
        equations = []
        equation_symbols = []
        equation_symbol_lines = []
        if len([line for line in bl if line.strip()]) > 1:
            for i in range(len(bl)):
                line = bl[i].strip()
                match i:
                    case 0:
                        subject = line
                    case 1:
                        context = f"In [{line}], " if line != "" else ""
                    case 2:
                        symbol = line
                    case 3:
                        symbol += f" ({line})" if line != "" else ""
                    case 4:
                        definition = line
                    case 5:
                        equations = self.split_equations(line.strip(), symbol)
                        equation_string = (
                            f" and is given by [{line}]" if line != "" else ""
                        )
                    case 6:
                        units = (
                            f" [with units {line}"
                            if line != "unitless"
                            else " [(unitless)"
                        )
                    case 7:
                        units += (
                            f" {line}::units]" if line != "========" else "::units]"
                        )
                    case _:
                        if line == "========":
                            break

                        if line.count("||") == 3:
                            split_line = line[2:].split("||")
                            equation_symbol_lines.append(line)
                            equation_symbols.append([
                                split_line[0],
                                split_line[2],
                                split_line[3],
                            ])

            newbuf = self.buffer.replace("\n\n", "\n").split("\n========\n")
            print(f"{getframeinfo(currentframe()).lineno} {newbuf=}")

            syms_per_buf = [
                "\n".join([line for line in buf.split("\n")[1:] if line])
                for buf in newbuf[1:]
            ]
            main_syms = len(set(syms_per_buf)) == 1

            for i, eqn in enumerate(equations):
                try:
                    if main_syms:
                        newbuf[i + 1] = (
                            f"\\({eqn}\\)\n{'\n'.join(equation_symbol_lines)}"
                        )
                    else:
                        newbuf[i + 1] = (
                            f"\\({eqn}\\)\n{'\n'.join(newbuf[i + 1].split('\n')[1:])}"
                        )
                except IndexError:
                    newbuf.append(f"\\({eqn}\\)\n{'\n'.join(equation_symbol_lines)}")

            print(f"{getframeinfo(currentframe()).lineno} {newbuf=}")

            newbufstr = "\n========\n".join(newbuf)
            print(f"{getframeinfo(currentframe()).lineno} {buffer=}")
            print(f"{getframeinfo(currentframe()).lineno} {self.buffer=}")
            if buffer == self.buffer:
                self.buffer = newbufstr
                self.threadpool.start(BufferWrite().buffer_write(newbufstr))

            note_0 = self.notes[0]
            c = count(1)
            note_0_text = f"{context}[{subject}] [{symbol}] is defined as [{definition}]{equation_string} {units}."
            note_0_text = self.capitalise(note_0_text)
            while (match := re.search(r"\[([^\]]+)\]", note_0_text)) is not None:
                note_0_text = note_0_text.replace(
                    f"{match.group(0)}",
                    "{{c" + str(next(c)) + f"::{match.group(0)[1:-1]}" + "}}",
                )

            note_0.text = note_0_text
            self.web_views[0].setHtml(note_0.html())

            right_notes_length = 1 + (len(equations) * 2)
            adding_notes = int((right_notes_length - len(self.notes)) / 2)

            if adding_notes > 0:
                for _ in range(adding_notes):
                    self.add_notes([[1, Cloze], [1, Basic_And_Reversed]])

                    for button in self.buttons[1:]:
                        try:
                            self.tabButtons.removeWidget(button)
                            button.deleteLater()
                            button = None
                        except RuntimeError:
                            pass

                    for i in range(1, len(equations) * 2 + 1, 2):
                        button = QPushButton(f"Cloze {int((i - 1) / 2)}")
                        button.pressed.connect(lambda: self.switch_web_view(i))
                        self.buttons.append(button)
                        self.tabButtons.addWidget(button)

                        button = QPushButton(f"BnR {int((i - 1) / 2)}")
                        button.pressed.connect(lambda: self.switch_web_view(i + 1))
                        self.buttons.append(button)
                        self.tabButtons.addWidget(button)

                    self.switch_web_view("all")

            for i in range(1, len(self.notes[1:]) + 1, 2):
                eqn_no = int((i + 1) / 2)
                bufseg = newbuf[eqn_no]
                bufseg_lines = bufseg.split("\n")
                eqn = bufseg_lines[0]
                eqn_str = f" is given by {eqn}"
                eqn_symb = []
                for line in [
                    line for line in bufseg_lines[1:] if line.count("||") == 3
                ]:
                    split_line = line[2:].split("||")
                    eqn_symb.append([split_line[0], split_line[2], split_line[3]])

                match len(eqn_symb):
                    case 0:
                        note_1_eqn_symb_str = "."
                        note_2_eqn_symb_str = ""
                    case 1:
                        note_1_eqn_symb_str = f", where [{eqn_symb[0][0]}] is [{eqn_symb[0][1]} {eqn_symb[0][2]}]."
                        note_2_eqn_symb_str = f"{eqn_symb[0][1]}"
                    case 2:
                        note_1_eqn_symb_str = ", where\n\n"
                        for pair in eqn_symb:
                            note_1_eqn_symb_str += (
                                f" - [{pair[0]}] is [{pair[1]} {pair[2]}]\n"
                            )

                        randomised_symbols = random.sample(
                            [symbol[1] for symbol in eqn_symb], k=len(eqn_symb)
                        )
                        randomised_symbols.insert(len(randomised_symbols) - 1, "and")
                        note_2_eqn_symb_str = " ".join([
                            f"{symbol}" for symbol in randomised_symbols
                        ])
                    case _:
                        note_1_eqn_symb_str = ", where\n\n"
                        for pair in eqn_symb:
                            note_1_eqn_symb_str += (
                                f" - [{pair[0]}] is [{pair[1]} {pair[2]}]\n"
                            )

                        randomised_symbols = random.sample(
                            [symbol[1] for symbol in eqn_symb], k=len(eqn_symb)
                        )
                        randomised_symbols.insert(len(randomised_symbols) - 1, "and")
                        note_2_eqn_symb_str = ", ".join([
                            f"${symbol}$" for symbol in randomised_symbols
                        ])
                        note_2_eqn_symb_str = note_2_eqn_symb_str.replace(
                            "$and$,", "and"
                        ).replace("$", "")

                note_1_text = f"{context}[{subject}]{eqn_str}{note_1_eqn_symb_str}"
                note_1_text = self.capitalise(note_1_text)

                c = count(1)
                while (match := re.search(r"\[([^\]]+)\]", note_1_text)) is not None:
                    note_1_text = note_1_text.replace(
                        f"{match.group(0)}",
                        "{{c" + str(next(c)) + f"::{match.group(0)[1:-1]}" + "}}",
                    )

                note_1 = self.notes[i]
                if note_1.text != note_1_text:
                    self.notes[i] = Cloze(note_1_text)
                    self.web_views[i].setHtml(self.notes[i].html())

                note_2_front = f"{subject} {symbol}, given {note_2_eqn_symb_str}."
                note_2_front = self.capitalise(note_2_front)

                note_2_back = eqn

                note_2 = self.notes[i + 1]
                if note_2.front != note_2_front or note_2.back != note_2_back:
                    note_2.front = note_2_front
                    note_2.back = note_2_back
                    self.web_views[i + 1].setHtml(note_2.html())

            self.temp_output_file.seek(0)
            for note in self.notes:
                self.temp_output_file.write(str(note).encode("utf-8"))


class Equation(NoteGenerator):
    def __init__(self):
        super().__init__()
        self.name = "Equation"
        self.setWindowTitle(self.name)
        self.output_file = f"{self.subject}equations.md"
        self.template = "anki-equation"

        self.set_number_of_notes([[1, Cloze], [1, Basic_And_Reversed]])
        self.switch_web_view("all")

        formula_cloze_button = QPushButton("Formula Cloze")
        formula_cloze_button.pressed.connect(lambda: self.switch_web_view(0))
        self.tabButtons.addWidget(formula_cloze_button)

        formula_basic_and_reversed_button = QPushButton("Formula BnR")
        formula_basic_and_reversed_button.pressed.connect(
            lambda: self.switch_web_view(1)
        )
        self.tabButtons.addWidget(formula_basic_and_reversed_button)

    def update_web_view(self, buffer: str):
        if buffer == self.buffer or buffer == self.last_buffer:
            return

        self.last_buffer = buffer

        if self.displaying == -1:
            self.buffer = buffer

        bl = buffer.split("\n")
        if bl[0].startswith("# Note"):
            if bl[1].strip() == "model: Cloze":
                self.notes[self.displaying] = Cloze()
                for i in range(len(bl[1:])):
                    if bl[i].replace(" ", "") == "##Text":
                        for line in bl[i + 1 :]:
                            if line.replace(" ", "") == "##BackExtra":
                                break
                            self.notes[self.displaying].text += f"\n{line.strip()}"
                    elif bl[i].replace(" ", "") == "##BackExtra":
                        for line in bl[i + 1 :]:
                            self.notes[
                                self.displaying
                            ].back_extra += f"\n{line.strip()}"
            elif (
                bl[1].strip() == "model: Basic"
                or bl[1].strip() == "model: Basic (and reversed card)"
            ):
                self.notes[self.displaying].front = ""
                self.notes[self.displaying].back = ""
                for i in range(len(bl[1:])):
                    if bl[i].replace(" ", "") == "##Front":
                        for line in bl[i + 1 :]:
                            if line.replace(" ", "") == "##Back":
                                break
                            self.notes[self.displaying].front += f"\n{line.strip()}"
                    elif bl[i].replace(" ", "") == "##Back":
                        for line in bl[i + 1 :]:
                            self.notes[self.displaying].back += f"\n{line.strip()}"

            self.web_views[self.displaying].setHtml(self.notes[self.displaying].html())

            self.temp_output_file.seek(0)
            for note in self.notes:
                self.temp_output_file.write(str(note).encode("utf-8"))

            return

        equation_symbols = []
        if len(bl) > 1:
            for i in range(len(bl)):
                line = bl[i].strip()
                match i:
                    case 0:
                        subject = line
                    case 1:
                        context = f"In [{line}], " if line != "" else ""
                    case 2:
                        symbol = line
                    case 3:
                        symbol += f" ({line})" if line != "" else ""
                    case 4:
                        units = f" in {line}" if line != "unitless" else " (unitless)"
                    case 5:
                        equation = f" is given by {line}" if line != "" else ""
                    case _:
                        if line.count("||") == 3:
                            split_line = line.split("||")
                            equation_symbols.append([
                                split_line[0][2:],
                                split_line[2],
                                split_line[3],
                            ])

            note_0 = self.notes[0]
            match len(equation_symbols):
                case 0:
                    note_0_equation_symbol_string = "."
                    note_1_equation_symbol_string = ""
                case 1:
                    note_0_equation_symbol_string = f", where [{equation_symbols[0][0]}] is [{equation_symbols[0][1]} {equation_symbols[0][2]}]."
                    note_1_equation_symbol_string = f"{equation_symbols[0][1]}"
                case 2:
                    note_0_equation_symbol_string = ", where\n\n"
                    for pair in equation_symbols:
                        note_0_equation_symbol_string += (
                            f" - [{pair[0]}] is [{pair[1]} {pair[2]}]\n"
                        )

                    randomised_symbols = random.sample(
                        [symbol[1] for symbol in equation_symbols],
                        k=len(equation_symbols),
                    )
                    randomised_symbols.insert(len(randomised_symbols) - 1, "and")
                    note_1_equation_symbol_string = " ".join([
                        f"{symbol}" for symbol in randomised_symbols
                    ])
                case _:
                    note_0_equation_symbol_string = ", where\n\n"
                    for pair in equation_symbols:
                        note_0_equation_symbol_string += (
                            f" - [{pair[0]}] is [{pair[1]} {pair[2]}]\n"
                        )

                    randomised_symbols = random.sample(
                        [symbol[1] for symbol in equation_symbols],
                        k=len(equation_symbols),
                    )
                    randomised_symbols.insert(len(randomised_symbols) - 1, "and")
                    note_1_equation_symbol_string = ", ".join([
                        f"${symbol}$" for symbol in randomised_symbols
                    ])
                    note_1_equation_symbol_string = (
                        note_1_equation_symbol_string.replace("$and$,", "and").replace(
                            "$", ""
                        )
                    )

            note_0_text = f"{context}[{subject} {symbol}{units}]{equation}{note_0_equation_symbol_string}"
            note_0_text = self.capitalise(note_0_text)

            c = count(1)
            while (match := re.search(r"\[([^\]]+)\]", note_0_text)) is not None:
                note_0_text = note_0_text.replace(
                    f"{match.group(0)}",
                    "{{c" + str(next(c)) + f"::{match.group(0)[1:-1]}" + "}}",
                )

            if note_0.text != note_0_text:
                note_0.text = note_0_text
                self.web_views[0].setHtml(note_0.html())

            note_1 = self.notes[1]
            note_1_front = (
                f"{subject} {symbol}{units}, given {note_1_equation_symbol_string}."
            )
            note_1_front = self.capitalise(note_1_front)

            note_1_back = equation[12:]

            if note_1.front != note_1_front or note_1.back != note_1_back:
                note_1.front = note_1_front
                note_1.back = note_1_back
                self.web_views[1].setHtml(note_1.html())

            self.temp_output_file.seek(0)
            for note in self.notes:
                self.temp_output_file.write(str(note).encode("utf-8"))
