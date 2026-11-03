import copy
import itertools
import os
import pathlib
import random
import re
import signal
import sqlite3
import subprocess
import tempfile
import time
from functools import partial
from inspect import currentframe, getframeinfo, stack
from itertools import count

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
from autoanki.notes import Basic, BasicAndReversed, Cloze

Note = type[Basic] | type[BasicAndReversed] | type[Cloze]
NoteObj = Basic | Cloze


class NoteGenerator(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.deck = ""
        self.subject = ""
        self.note_width: int = 500
        self.note_height = 300

        self.temp_file = tempfile.NamedTemporaryFile(suffix=".tex")
        self.temp_file_name: str = self.temp_file.name
        self.buffer = "\n"
        self.last_buffer = ""
        self.displaying: int = -1

        self.layout: QVBoxLayout = QVBoxLayout()
        self.margins: list[int] = [10, 10, 10, 10]  # left, top, right, bottom
        self.layout.setContentsMargins(self.margins[0], self.margins[1], self.margins[2], self.margins[3])
        self.spacing = 10
        self.layout.setSpacing(self.spacing)

        self.note_display_grid = QGridLayout()
        self.layout.addLayout(self.note_display_grid)

        self.notes: list[NoteObj] = []

        self.tabButtons = QHBoxLayout()
        all_button = QPushButton("All")
        all_button.pressed.connect(lambda: self.switch_note_display(-1))
        self.buttons: list[QPushButton] = [all_button]
        self.tabButtons.addWidget(all_button)

        self.layout.addLayout(self.tabButtons)

        self.setLayout(self.layout)

        self.template = ""
        self.editor = subprocess.Popen([
            "kitty",
            "nvim",
            "--listen",
            "/tmp/nvim.sock",
            self.temp_file_name,
        ])
        time.sleep(0.5)  # gives the process time to start before performing the first write to the buffer

        self.threadpool = QThreadPool()
        self.timer = QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.spawn)
        self.timer.start()

    @staticmethod
    def update_cloze(bl: list[str], note: Cloze) -> bool:
        old_note = copy.deepcopy(note)
        note.text = ""
        note.back_extra = ""
        if not [line for line in bl if line.startswith("nid:")]:
            note.nid = -1
        for i in range(len(bl[1:])):
            if bl[i].replace(" ", "") == "##Text":
                for line in bl[i + 1 :]:
                    if line.replace(" ", "") == "##BackExtra":
                        break
                    note.text += f"\n{line.strip()}"
            elif bl[i].replace(" ", "") == "##BackExtra":
                for line in bl[i + 1 :]:
                    note.back_extra += f"\n{line.strip()}"

        return note.text != old_note.text or note.back_extra != old_note.back_extra

    @staticmethod
    def update_basic(bl: list[str], note: Basic) -> bool:
        old_note = copy.deepcopy(note)
        note.front = ""
        note.back = ""
        if not [line for line in bl if line.startswith("nid:")]:
            note.nid = -1
        for i in range(len(bl[1:])):
            if bl[i].replace(" ", "") == "##Front":
                for line in bl[i + 1 :]:
                    if line.replace(" ", "") == "##Back":
                        break
                    note.front += f"\n{line.strip()}"
            elif bl[i].replace(" ", "") == "##Back":
                for line in bl[i + 1 :]:
                    note.back += f"\n{line.strip()}"

        return note.front != old_note.front or note.back != old_note.back

    def update_single_note(self, bl: list[str], note: NoteObj) -> bool:
        if isinstance(note, Cloze):
            return self.update_cloze(bl, note)
        if isinstance(note, Basic):
            return self.update_basic(bl, note)

    def parse_user_segment_of_buffer(self, template_length: int, buffer: str):
        bl = buffer.split("\n")
        self.subject = bl[0].strip()
        self.context = f"In [{bl[1].strip()}], " if bl[1].strip() else ""
        self.symbol = bl[2].strip()
        equations = self.split_equations(bl[5].strip(), bl[2].strip())

        equation_symbol_lines = []
        equation_symbols = []
        for line in bl[template_length:]:
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
        return equations, equation_symbol_lines

    def assemble_summary_cloze(self, bl: list[str]) -> None:
        symbol_name = f" ({bl[3].strip()})" if bl[3].strip() else ""
        definition = bl[4].strip()
        equation_string = f" and is given by [{bl[5].strip()}]" if bl[5].strip() else ""
        units = f" [with units {bl[6].strip()}" if bl[6].strip() != "unitless" else " [(unitless)"
        units += f" {bl[7].strip()}::units]" if bl[7].strip() else "::units]"

        summary_cloze = self.notes[0]
        c = count(1)
        summary_cloze_text = f"{self.context}[{self.subject}] [{self.symbol} {symbol_name}] is defined as [{definition}]{equation_string} {units}."
        summary_cloze_text = self.capitalise(summary_cloze_text)
        while (match := re.search(r"\[([^\]]+)\]", summary_cloze_text)) is not None:
            summary_cloze_text = summary_cloze_text.replace(
                f"{match.group(0)}",
                "{{c" + str(next(c)) + f"::{match.group(0)[1:-1]}" + "}}",
            )

        summary_cloze.text = summary_cloze_text

    def create_and_write_new_buffer_contents(self, equations: list[str], equation_symbol_lines: list[str]) -> list[str]:
        newbuf = self.buffer.replace("\n\n", "\n").split("\n========\n")

        syms_per_buf = ["\n".join([line for line in buf.split("\n")[1:] if line]) for buf in newbuf[1:]]
        main_syms = len(set(syms_per_buf)) == 1

        for i, eqn in enumerate(equations):
            try:
                if main_syms:
                    newbuf[i + 1] = f"\\({eqn}\\)\n{'\n'.join(equation_symbol_lines)}"
                else:
                    newbuf[i + 1] = f"\\({eqn}\\)\n{'\n'.join(newbuf[i + 1].split('\n')[1:])}"
            except IndexError:
                newbuf.append(f"\\({eqn}\\)\n{'\n'.join(equation_symbol_lines)}")

        newbufstr = "\n========\n".join(newbuf).strip("\n")
        print(f"{__file__}:{getframeinfo(currentframe()).lineno} {stack()[0][3]}() {len(newbuf)=}")
        if self.displaying == -1:
            self.buffer = newbufstr
            self.threadpool.start(BufferWrite().buffer_write(newbufstr))

        return newbuf

    def check_number_of_notes_is_correct(self, equations: list[str]) -> None:
        right_notes_length = 1 + (len(equations) * 2)
        adding_notes = int((right_notes_length - len(self.notes)) / 2)
        print(f"{__file__}:{getframeinfo(currentframe()).lineno} {stack()[0][3]}() {adding_notes=}")

        if adding_notes > 0:
            for _ in range(adding_notes):
                self.add_notes([[1, Cloze], [1, BasicAndReversed]])

                for i in range(1, int(adding_notes / 2), 2):
                    pair_num = int((len(self.notes) - 1) / 2) + 1
                    button = QPushButton(f"Cloze {pair_num}")
                    button.pressed.connect(partial(self.switch_note_display, i))
                    self.buttons.append(button)
                    self.tabButtons.addWidget(button)

                    button = QPushButton(f"BnR {pair_num}")
                    button.pressed.connect(partial(self.switch_note_display, i + 1))
                    self.buttons.append(button)
                    self.tabButtons.addWidget(button)

        elif adding_notes < 0:
            while adding_notes < 0:
                adding_notes = int((right_notes_length - len(self.notes)) / 2)
                del self.notes[-1]
                last = self.tabButtons.itemAt(self.tabButtons.count() - 1)
                del last

    def set_content_of_equation_note_pairs(self, start_index: int, newbuf: list[str], equations: list[str]) -> None:
        for i in range(start_index, len(self.notes[start_index:]), 2):
            eqn_no = int((i + 1) / 2)
            bufseg = newbuf[eqn_no]
            bufseg_lines = bufseg.split("\n")
            eqn = bufseg_lines[0]
            eqn_str = f" {'is' if len(equations) == 1 else 'can be'} given by {eqn}"
            eqn_symb = []
            for line in [line for line in bufseg_lines[1:] if line.count("||") == 3]:
                split_line = line[2:].split("||")
                eqn_symb.append([split_line[0], split_line[2], split_line[3]])

            match len(eqn_symb):
                case 0:
                    equation_cloze_symbol_string = "."
                    equation_bnr_symbol_string = ""
                case 1:
                    equation_cloze_symbol_string = f", where [{eqn_symb[0][0]}] is [{eqn_symb[0][1]} {eqn_symb[0][2]}]."
                    equation_bnr_symbol_string = f"{eqn_symb[0][1]}"
                case 2:
                    equation_cloze_symbol_string = ", where\n\n"
                    for pair in eqn_symb:
                        equation_cloze_symbol_string += f" - [{pair[0]}] is [{pair[1]} {pair[2]}]\n"

                    randomised_symbols = random.sample([symbol[1] for symbol in eqn_symb], k=len(eqn_symb))
                    randomised_symbols.insert(len(randomised_symbols) - 1, "and")
                    equation_bnr_symbol_string = " ".join([f"{symbol}" for symbol in randomised_symbols])
                case _:
                    equation_cloze_symbol_string = ", where\n\n"
                    for pair in eqn_symb:
                        equation_cloze_symbol_string += f" - [{pair[0]}] is [{pair[1]} {pair[2]}]\n"

                    randomised_symbols = random.sample([symbol[1] for symbol in eqn_symb], k=len(eqn_symb))
                    randomised_symbols.insert(len(randomised_symbols) - 1, "and")
                    equation_bnr_symbol_string = ", ".join([f"${symbol}$" for symbol in randomised_symbols])
                    equation_bnr_symbol_string = equation_bnr_symbol_string.replace("$and$,", "and").replace("$", "")

            equation_cloze_text = f"{self.context}[{self.subject}]{eqn_str}{equation_cloze_symbol_string}"
            equation_cloze_text = self.capitalise(equation_cloze_text)

            c = count(1)
            while (match := re.search(r"\[([^\]]+)\]", equation_cloze_text)) is not None:
                equation_cloze_text = equation_cloze_text.replace(
                    f"{match.group(0)}",
                    "{{c" + str(next(c)) + f"::{match.group(0)[1:-1]}" + "}}",
                )

            equation_cloze = self.notes[i]
            if equation_cloze.text != equation_cloze_text:
                self.notes[i] = Cloze(equation_cloze_text)

            equation_bnr_front = f"{self.subject} {self.symbol}, given {equation_bnr_symbol_string}."
            equation_bnr_front = self.capitalise(equation_bnr_front)

            equation_bnr = self.notes[i + 1]
            if equation_bnr.front != equation_bnr_front or equation_bnr.back != eqn:
                equation_bnr.front = equation_bnr_front
                equation_bnr.back = eqn

    def update_web_view(self, buffer: str) -> None:
        pass

    def spawn(self) -> None:
        worker = BufferRead(self.temp_file)
        worker.signals.reload.connect(self.update_web_view)
        self.threadpool.start(worker.buffer_read(self.buffer))

    def set_number_of_notes(self, num: list[tuple[int, Note]]) -> None:
        self.notes: list[Note] = []
        self.add_notes(num)

    def add_notes(self, to_add: list[tuple[int, Note]]) -> None:
        for note_set in to_add:
            for _ in range(note_set[0]):
                self.notes.append(note_set[1]())

    def switch_note_display(self, notes: int) -> None:
        self.displaying: int = notes
        if notes == -1:
            notes_to_show: list[NoteObj] = self.notes
            self.threadpool.start(BufferWrite().buffer_write(self.buffer))
            notes_len: int = len(notes_to_show)
        else:
            notes_len = 1
            notes_to_show: list[NoteObj | None] = [None] * len(self.notes)
            notes_to_show[notes] = self.notes[notes]
            self.threadpool.start(BufferWrite().buffer_write(str(self.notes[notes])))

        # note_layouts[i] holds the layout for i many notes
        # each layout has the form [x, y]*however many notes
        note_layouts: list[list[list[int]]] = [
            [[0, 0]],  # 0
            [[0, 0]],  # 1
            [[0, 0], [0, 1]],  # 2
            [[0, 0], [0, 1], [0, 2]],  # 3
            [[0, 0], [0, 1], [1, 0], [1, 1]],  # 4
            [[0, 0, 1, 2], [0, 2, 1, 2], [0, 4, 1, 2], [1, 1, 1, 2], [1, 3, 1, 2]],  # 5
            [[0, 0, 1, 2], [0, 2, 1, 2], [0, 4, 1, 2], [1, 1, 1, 2], [1, 3, 1, 2]],
        ]
        grid_xy: list[list[int]] = [[], [1, 1], [2, 1], [3, 1], [2, 2], [3, 2]]

        while self.note_display_grid.count() > 0:
            view = self.note_display_grid.itemAt(0).widget()
            view.setParent(None)
            del view

        for i, note in enumerate(notes_to_show):
            if note is not None:
                note_wv = QWebEngineView()
                note_wv.setHtml(note.html())
                x: int = note_layouts[len(notes_to_show)][i][0]
                y: int = note_layouts[len(notes_to_show)][i][1]

                note_wv.setFixedSize(self.note_width, self.note_height)
                note_wv.resize(self.note_width, self.note_height)
                note_wv.show()
                if len(note_layouts[len(notes_to_show)][i]) > 2:
                    x2: int = note_layouts[len(notes_to_show)][i][2]
                    y2: int = note_layouts[len(notes_to_show)][i][3]
                    self.note_display_grid.addWidget(note_wv, x, y, x2, y2)
                else:
                    self.note_display_grid.addWidget(note_wv, x, y)

        window_width = (grid_xy[notes_len][0] * (self.note_width + self.spacing)) - self.spacing + self.margins[0] + self.margins[2]
        window_height = (grid_xy[notes_len][1] * (self.note_height + self.spacing)) + 50 + self.margins[1] + self.margins[2]
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
        os.kill(self.editor.pid, signal.SIGINT)
        if self.buffer.replace("\n", "").strip():
            for note in self.notes:
                write_file = tempfile.NamedTemporaryFile(suffix=".tex")
                with pathlib.Path(write_file.name).open("w") as f:
                    f.write(str(note))
                    f.seek(0)

                subprocess.run([
                    "apy",
                    "update-from-file",
                    "-d",
                    self.deck,
                    "-u",
                    write_file.name,
                ])

                with pathlib.Path(write_file.name).open("r") as f:
                    note_str = f.read()

                notesplit = note_str.split("\n")
                print(f"{__file__}:{getframeinfo(currentframe()).lineno} {stack()[0][3]}() {notesplit=}")
                nidlines = [line[4:].strip() for line in notesplit if line.startswith("nid")]
                print(f"{__file__}:{getframeinfo(currentframe()).lineno} {stack()[0][3]}() {nidlines=}")

                note.nid = nidlines[0]
                print(f"{__file__}:{getframeinfo(currentframe()).lineno} {stack()[0][3]}() {note.nid=}")
                if note.nid < 0:
                    print(f"{__file__}:{getframeinfo(currentframe()).lineno} {stack()[0][3]}() {note_str=}")
                    print(f"{__file__}:{getframeinfo(currentframe()).lineno} {stack()[0][3]}() {note=}")
                    raise ValueError

            with sqlite3.connect("notes.db") as conn:
                c = conn.cursor()
                c.execute("""BEGIN TRANSACTION;""")
                try:
                    if hasattr(self, "id"):
                        c.execute(
                            """INSERT OR REPLACE INTO buffers(id, buffer, type, deck) VALUES (?, ?, ?, ?)""",
                            (self.id, self.buffer, self.template[5:], self.deck),
                        )
                    else:
                        c.execute(
                            """INSERT OR REPLACE INTO buffers(buffer, type, deck) VALUES (?, ?, ?)""",
                            (self.buffer, self.template[5:], self.deck),
                        )

                    buffer_id = c.lastrowid
                    for i, note in enumerate(self.notes):
                        print(f"{__file__}:{getframeinfo(currentframe()).lineno} {stack()[0][3]}() {i=} {note.nid=}")
                        if isinstance(note, BasicAndReversed):
                            c.execute(
                                """INSERT OR REPLACE INTO basicandreversed VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    note.nid,
                                    self.deck,
                                    note.tags,
                                    note.front,
                                    note.back,
                                    i,
                                    buffer_id,
                                ),
                            )
                        elif isinstance(note, Basic):
                            c.execute(
                                """INSERT OR REPLACE INTO basic VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    note.nid,
                                    self.deck,
                                    note.tags,
                                    note.front,
                                    note.back,
                                    i,
                                    buffer_id,
                                ),
                            )
                        elif isinstance(note, Cloze):
                            c.execute(
                                """INSERT OR REPLACE INTO cloze VALUES(?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    note.nid,
                                    self.deck,
                                    note.tags,
                                    note.text,
                                    note.back_extra,
                                    i,
                                    buffer_id,
                                ),
                            )
                        else:
                            print(f"{getframeinfo(currentframe()).lineno} {type(note)=}")

                    c.execute("""COMMIT;""")
                except sqlite3.IntegrityError as e:
                    c.execute("""ROLLBACK;""")
                    raise e
            conn.close()


class SingleBasic(NoteGenerator):
    def __init__(self, deck: str, id: int = -1, buffer: str = "", notes=[]) -> None:
        super().__init__()
        self.notes: list[Basic]
        if id != -1:
            self.id = id

        if buffer:
            self.buffer = buffer
        else:
            self.buffer = ""

        if notes:
            self.notes = notes
            for _ in range(len(notes)):
                wv = QWebEngineView()
                self.web_views.append(wv)
                self.note_display_grid.addWidget(wv)
        else:
            self.set_number_of_notes([(1, Basic)])

        self.name = "Basic Note"
        self.setWindowTitle(self.name)
        self.deck = deck
        self.output_file = f"{self.deck.split('::')[-1].lower().replace(' ', '-')}-basic-notes.md"

        self.switch_note_display(-1)

    def update_web_view(self, buffer: str) -> None:
        if buffer == self.buffer + "\n":
            return

        buffer = buffer.replace("<mathjax>", "").replace("</mathjax>", "")
        bl = buffer.split("\n")
        note = self.notes[0]

        self.buffer = buffer

        front = bl[0]
        self.subject = front
        back = bl[1]
        if note.front != front or note.back != back:
            note.front = front
            note.back = back
            self.switch_note_display(-1)


class SingleBnR(SingleBasic):
    def __init__(self, deck: str, id: int = -1, buffer: str = "", notes=[]) -> None:
        super().__init__(deck, id, buffer, notes)
        if buffer:
            self.buffer = buffer
        self.notes: list[BasicAndReversed]
        self.name = "Basic (and reversed) Note"
        self.setWindowTitle(self.name)

        if notes:
            self.notes = notes
            wv = QWebEngineView()
            self.web_views.append(wv)
            self.note_display_grid.addWidget(wv)
        else:
            self.set_number_of_notes([(1, BasicAndReversed)])


class Definition(NoteGenerator):
    def __init__(self, deck: str, id: int = -1, buffer: str = "", notes=[]) -> None:
        super().__init__()
        time.sleep(0.5)
        if id != -1:
            self.id = id
        self.template = "anki-definition"
        if buffer:
            self.buffer = buffer
        else:
            self.buffer = self.template

        if notes:
            exp_note_types = [Cloze] + [Cloze, BasicAndReversed] * int((len(notes) - 1) / 2)
            note_types = [type(note) for note in notes]

            if exp_note_types == note_types:
                print(f"{__file__}:{getframeinfo(currentframe()).lineno} {stack()[0][3]}() Given notes, and the notes are good.")
                self.notes = notes
                num_card_pairs = itertools.count(1)

                button = QPushButton("Summary Cloze")
                button.pressed.connect(partial(self.switch_note_display, 0))
                self.buttons.append(button)
                self.tabButtons.addWidget(button)

                for i in range(1, int((len(notes) + 1) / 2)):
                    disp_num = next(num_card_pairs)
                    button = QPushButton(f"Cloze {disp_num}")
                    button.pressed.connect(partial(self.switch_note_display, i + 1))
                    self.buttons.append(button)
                    self.tabButtons.addWidget(button)

                    button = QPushButton(f"BnR {disp_num}")
                    button.pressed.connect(partial(self.switch_note_display, i + 2))
                    self.buttons.append(button)
                    self.tabButtons.addWidget(button)
            else:
                self.set_default_notes()
        else:
            self.set_default_notes()

        self.switch_note_display(-1)
        self.name = "Definition"
        self.setWindowTitle(self.name)
        self.deck = deck
        self.output_file = f"{deck.rsplit('::', maxsplit=1)[-1].lower().replace(' ', '-')}-definitions.md"
        self.template = "anki-definition"

    def set_default_notes(self) -> None:
        self.base_notes: list[tuple[int, Note]] = [
            (2, Cloze),
            (1, BasicAndReversed),
        ]
        self.set_number_of_notes(self.base_notes)
        definition_cloze_button = QPushButton("Summary Cloze")
        definition_cloze_button.pressed.connect(lambda: self.switch_note_display(0))
        self.buttons.append(definition_cloze_button)
        self.tabButtons.addWidget(definition_cloze_button)

        formula_cloze_button = QPushButton("Formula Cloze")
        formula_cloze_button.pressed.connect(lambda: self.switch_note_display(1))
        self.buttons.append(formula_cloze_button)
        self.tabButtons.addWidget(formula_cloze_button)

        formula_basic_and_reversed_button = QPushButton("Formula BnR")
        formula_basic_and_reversed_button.pressed.connect(lambda: self.switch_note_display(2))
        self.buttons.append(formula_basic_and_reversed_button)
        self.tabButtons.addWidget(formula_basic_and_reversed_button)

    def update_web_view(self, buffer: str) -> None:
        if buffer == self.buffer + "\n":
            return

        if self.displaying != -1:
            bl = buffer.split("\n")
            this_note = self.notes[self.displaying]
            if self.update_single_note(bl, this_note):
                self.switch_note_display(self.displaying)

            return

        self.buffer = buffer
        buffer = buffer.replace("{{", "{ {").replace("}}", "} }")
        bl = buffer.split("\n")
        equations, equation_symbol_lines = self.parse_user_segment_of_buffer(8, buffer.split("========")[0])
        self.assemble_summary_cloze(bl[:8])
        newbuf = self.create_and_write_new_buffer_contents(equations, equation_symbol_lines)
        self.check_number_of_notes_is_correct(equations)
        self.set_content_of_equation_note_pairs(1, newbuf, equations)
        self.switch_note_display(-1)


class Equation(NoteGenerator):
    def __init__(self, deck: str, id: int = -1, buffer: str = "", notes=[]) -> None:
        super().__init__()
        self.name = "Equation"
        self.setWindowTitle(self.name)
        self.deck = deck
        self.template = "anki-equation"

        if id != -1:
            self.id = id
        if buffer:
            self.buffer = buffer
        else:
            self.buffer = self.template

        if notes:
            exp_note_types = [Cloze, BasicAndReversed] * int(len(notes) / 2)
            note_types = [type(note) for note in notes]

            if exp_note_types == note_types:
                self.notes = notes
                num_card_pairs = itertools.count(1)

                for i in range(int(len(notes) / 2)):
                    disp_num = next(num_card_pairs)
                    button = QPushButton(f"Cloze {disp_num}")
                    button.pressed.connect(partial(self.switch_note_display, i))
                    self.buttons.append(button)
                    self.tabButtons.addWidget(button)

                    button = QPushButton(f"BnR {disp_num}")
                    button.pressed.connect(partial(self.switch_note_display, i + 1))
                    self.buttons.append(button)
                    self.tabButtons.addWidget(button)
            else:
                self.set_default_notes()
        else:
            self.set_default_notes()

        self.switch_note_display(-1)
        self.threadpool.start(BufferWrite().buffer_write(self.buffer))

    def set_default_notes(self) -> None:
        self.set_number_of_notes([[1, Cloze], [1, BasicAndReversed]])

        summary_cloze_button = QPushButton("Formula Cloze")
        summary_cloze_button.pressed.connect(lambda: self.switch_note_display(0))
        self.tabButtons.addWidget(summary_cloze_button)

        formula_basic_and_reversed_button = QPushButton("Formula BnR")
        formula_basic_and_reversed_button.pressed.connect(lambda: self.switch_note_display(1))
        self.tabButtons.addWidget(formula_basic_and_reversed_button)

    def update_web_view(self, buffer: str) -> None:
        if buffer == self.buffer + "\n" or buffer == self.buffer:
            return

        if self.displaying != -1:
            bl = buffer.split("\n")
            this_note = self.notes[self.displaying]
            if self.update_single_note(bl, this_note):
                self.switch_note_display(self.displaying)

            return

        self.buffer = buffer
        buffer = buffer.replace("{{", "{ {").replace("}}", "} }")
        equations, equation_symbol_lines = self.parse_user_segment_of_buffer(6, buffer.split("========")[0])
        print(f"{__file__}:{getframeinfo(currentframe()).lineno} {stack()[0][3]}() {equations=}")
        equation_raw_data = [f"\\({equation}\\)\n{'\n'.join(equation_symbol_lines)}" for equation in equations]

        self.set_content_of_equation_note_pairs(0, equation_raw_data, equations)
        self.switch_note_display(-1)
