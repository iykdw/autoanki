import random
import re
import subprocess
import tempfile
from itertools import count

from PySide6.QtCore import QThreadPool, QTimer
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from autoanki.editor_interface import BufferRead, BufferWrite
from autoanki.notes import Basic, Basic_And_Reversed, Cloze


class NoteGenerator(QWidget):
    def __init__(self):
        super().__init__()
        self.note_width = 500
        self.note_height = 300

        self.threadpool = QThreadPool()
        self.timer = QTimer()
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.spawn)
        self.timer.start()

        self.file = tempfile.NamedTemporaryFile(suffix=".tex")
        self.buffer = ""
        self.last_buffer = ""
        self.displaying = "all"

        self.layout = QVBoxLayout()
        self.margins = [10, 10, 10, 10]  # left, top, right, bottom
        self.layout.setContentsMargins(self.margins[0], self.margins[1], self.margins[2], self.margins[3])
        self.spacing = 10
        self.layout.setSpacing(self.spacing)

        self.webViewGrid = QGridLayout()
        self.webViews = []

        self.notes = []
        self.output_file = "autoanki.md"
        self.temp_output_file = tempfile.TemporaryFile()

        self.layout.addLayout(self.webViewGrid)

        self.tabButtons = QHBoxLayout()
        all_button = QPushButton("All")
        all_button.pressed.connect(lambda: self.switchWebView("all"))
        self.tabButtons.addWidget(all_button)

        self.layout.addLayout(self.tabButtons)

        self.setLayout(self.layout)

        subprocess.call(
            ["kitten", "@", "launch", "--type", "os-window", "--title", "anki-nvim", "nvim", "--listen", "/tmp/nvim.sock", self.file.name]
        )

    def spawn(self):
        worker = BufferRead(self.file)
        worker.signals.reload.connect(self.updateWebView)
        self.threadpool.start(worker.buffer_read(self.buffer))

    def set_number_of_notes(self, num):
        self.notes = []
        self.webViews = []
        for _, notetype in enumerate(num):
            for _ in range(notetype[0]):
                self.webViews.append(QWebEngineView())
                self.notes.append(notetype[1]())

    def switchWebView(self, notes):
        self.displaying = notes if isinstance(notes, int) else -1
        if notes == "all":
            notes_to_show = self.notes
            self.threadpool.start(BufferWrite().buffer_write(self.buffer))
            notes_len = len(notes_to_show)
        else:
            notes_len = 1
            notes_to_show = [None] * len(self.notes)
            notes_to_show[notes] = self.notes[notes]
            self.threadpool.start(BufferWrite().buffer_write(str(self.notes[notes])))

        # note_layouts[i] holds the layout for i many notes
        # each layout has the form [x, y]*however many notes
        note_layouts = [[], [[0, 0]], [[0, 0], [0, 1]], [[0, 0], [0, 1], [0, 2]]]
        grid_xy = [[], [1, 1], [2, 1], [3, 1]]

        for vw in self.webViews:
            self.webViewGrid.removeWidget(vw)
            vw.hide()

        for i, note in enumerate(notes_to_show):
            if note is not None:
                webView = self.webViews[i]
                webView.setHtml(note.html())
                x = note_layouts[len(notes_to_show)][i][0]
                y = note_layouts[len(notes_to_show)][i][1]

                webView.setFixedSize(self.note_width, self.note_height)
                webView.resize(self.note_width, self.note_height)
                webView.show()
                self.webViewGrid.addWidget(webView, x, y)

        window_width = (grid_xy[notes_len][0] * (self.note_width + self.spacing)) - self.spacing + self.margins[0] + self.margins[2]
        window_height = (grid_xy[notes_len][1] * (self.note_height + self.spacing)) + 50 + self.margins[1] + self.margins[2]
        self.resize(window_width, window_height)

    def capitalise(self, text: str):
        for i in range(len(text)):
            if text[i].isalpha():
                return f"{text[:i]}{text[i].upper()}{text[i + 1 :]}"

        return text

    def closeEvent(self, event):
        self.threadpool.start(BufferWrite().buffer_write(""))
        self.temp_output_file.seek(0)
        with open(self.output_file, "a") as f:
            f.write(self.temp_output_file.read().decode("utf-8"))


class SingleBasic(NoteGenerator):
    def __init__(self):
        super().__init__()
        self.name = "Basic Note"
        self.setWindowTitle(self.name)
        self.output_file = "basic-notes.md"
        self.template = ""

        self.set_number_of_notes([[1, Basic]])
        self.switchWebView("all")

    def updateWebView(self, buffer: str):
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
                self.webViews[0].setHtml(self.notes[0].html())

            self.temp_output_file.seek(0)
            for note in self.notes:
                self.temp_output_file.write(str(note).encode("utf-8"))


class MathsIdentity(NoteGenerator):
    def __init__(self):
        super().__init__()
        self.name = "Maths Identity"
        self.setWindowTitle(self.name)
        self.output_file = "maths-identities.md"
        self.template = "anki-maths-identity"
        self.min_redraw_lines = 5

        self.set_number_of_notes([[2, Basic]])
        self.switchWebView("all")

        text_button = QPushButton("Text card")
        text_button.pressed.connect(lambda: self.switchWebView(0))
        self.tabButtons.addWidget(text_button)

        tex_button = QPushButton("Tex card")
        tex_button.pressed.connect(lambda: self.switchWebView(1))
        self.tabButtons.addWidget(tex_button)

    def updateWebView(self, buffer: str):
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
                self.webViews[0].setHtml(note_0.html())
            note_1 = self.notes[1]
            note_1_front = f"{bl[4]} {bl[1]} {bl[5]}"
            if note_1.front != note_1_front or note_1.back != note_01_back:
                note_1.front = note_1_front
                note_1.back = note_01_back
                self.webViews[1].setHtml(note_1.html())

            self.temp_output_file.seek(0)
            for note in self.notes:
                self.temp_output_file.write(str(note).encode("utf-8"))


class Definition(NoteGenerator):
    def __init__(self):
        super().__init__()
        self.name = "Definition"
        self.setWindowTitle(self.name)
        self.output_file = "definitions.md"
        self.template = "anki-definition"

        self.set_number_of_notes([[2, Cloze], [1, Basic_And_Reversed]])
        self.switchWebView("all")

        definition_cloze_button = QPushButton("Definition Cloze")
        definition_cloze_button.pressed.connect(lambda: self.switchWebView(0))
        self.tabButtons.addWidget(definition_cloze_button)

        formula_cloze_button = QPushButton("Formula Cloze")
        formula_cloze_button.pressed.connect(lambda: self.switchWebView(1))
        self.tabButtons.addWidget(formula_cloze_button)

        formula_basic_and_reversed_button = QPushButton("Formula BnR")
        formula_basic_and_reversed_button.pressed.connect(lambda: self.switchWebView(2))
        self.tabButtons.addWidget(formula_basic_and_reversed_button)

    def updateWebView(self, buffer: str):
        if buffer == self.buffer or buffer == self.last_buffer:
            return

        self.last_buffer = buffer

        if self.displaying == -1:
            self.buffer = buffer

        bl = buffer.split("\n")
        if bl[0].startswith("# Note"):
            if bl[1].strip() == "model: Cloze":
                self.notes[self.displaying].text = bl[5].strip()
                self.notes[self.displaying].back_extra = bl[8].strip()
            elif bl[1].strip() == "model: Basic" or bl[1].strip() == "model: Basic (and reversed card)":
                self.notes[self.displaying].front = bl[5].strip()
                self.notes[self.displaying].back = bl[8].strip()

            self.webViews[self.displaying].setHtml(self.notes[self.displaying].html())

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
                        definition = line
                    case 5:
                        equation = f" and is given by [{line}]" if line != "" else ""
                    case 6:
                        units = f" [with units {line}" if line != "unitless" else " [and is unitless"
                    case 7:
                        units += f" {line}::units]" if line != "" else "::units]"
                    case _:
                        if line.count("||") == 3:
                            split_line = line.split("||")
                            equation_symbols.append([split_line[0], split_line[2], split_line[3]])

            note_0 = self.notes[0]
            c = count(1)
            note_0_text = f"{context}[{subject}] [{symbol}] is defined as [{definition}]{equation}{units}."
            note_0_text = self.capitalise(note_0_text)
            while (match := re.search(r"\[([^\]]+)\]", note_0_text)) is not None:
                note_0_text = note_0_text.replace(f"{match.group(0)}", "{{c" + str(next(c)) + f"::{match.group(0)[1:-1]}" + "}}")

            if note_0.text != note_0_text:
                note_0.text = note_0_text
                self.webViews[0].setHtml(note_0.html())

            note_1 = self.notes[1]
            match len(equation_symbols):
                case 0:
                    note_1_equation_symbol_string = "."
                    note_2_equation_symbol_string = ""
                case 1:
                    note_1_equation_symbol_string = (
                        f", where [{equation_symbols[0][0]}] is [{equation_symbols[0][1]} {equation_symbols[0][2]}]."
                    )
                    note_2_equation_symbol_string = f"{equation_symbols[0][1]}"
                case 2:
                    note_1_equation_symbol_string = ", where\n\n"
                    for pair in equation_symbols:
                        note_1_equation_symbol_string += f" - [{pair[0]}] is [{pair[1]} {pair[2]}]\n"

                    randomised_symbols = random.sample([symbol[1] for symbol in equation_symbols], k=len(equation_symbols))
                    randomised_symbols.insert(len(randomised_symbols) - 1, "and")
                    note_2_equation_symbol_string = " ".join([f"{symbol}" for symbol in randomised_symbols])
                case _:
                    note_1_equation_symbol_string = ", where\n\n"
                    for pair in equation_symbols:
                        note_1_equation_symbol_string += f" - [{pair[0]}] is [{pair[1]} {pair[2]}]\n"

                    randomised_symbols = random.sample([symbol[1] for symbol in equation_symbols], k=len(equation_symbols))
                    randomised_symbols.insert(len(randomised_symbols) - 1, "and")
                    note_2_equation_symbol_string = ", ".join([f"${symbol}$" for symbol in randomised_symbols])
                    note_2_equation_symbol_string = note_2_equation_symbol_string.replace("$and$,", "and").replace("$", "")

            note_1_text = f"{context}[{subject if context == '' else subject}]{equation[4:]}{note_1_equation_symbol_string}"
            note_1_text = self.capitalise(note_1_text)

            c = count(1)
            while (match := re.search(r"\[([^\]]+)\]", note_1_text)) is not None:
                note_1_text = note_1_text.replace(f"{match.group(0)}", "{{c" + str(next(c)) + f"::{match.group(0)[1:-1]}" + "}}")

            if note_1.text != note_1_text:
                note_1.text = note_1_text
                self.webViews[1].setHtml(note_1.html())

            note_2 = self.notes[2]
            note_2_front = f"{definition} {symbol}, given {note_2_equation_symbol_string}."
            note_2_front = self.capitalise(note_2_front)

            note_2_back = equation
            note_2_back = note_2_back.split("[")[1].split("]")[0]

            if note_2.front != note_2_front or note_2.back != note_2_back:
                note_2.front = note_2_front
                note_2.back = note_2_back
                self.webViews[2].setHtml(note_2.html())

            self.temp_output_file.seek(0)
            for note in self.notes:
                self.temp_output_file.write(str(note).encode("utf-8"))


class Equation(NoteGenerator):
    def __init__(self):
        super().__init__()
        self.name = "Equation"
        self.setWindowTitle(self.name)
        self.output_file = "equation.md"
        self.template = "anki-equation"

        self.set_number_of_notes([[1, Cloze], [1, Basic_And_Reversed]])
        self.switchWebView("all")

        formula_cloze_button = QPushButton("Formula Cloze")
        formula_cloze_button.pressed.connect(lambda: self.switchWebView(0))
        self.tabButtons.addWidget(formula_cloze_button)

        formula_basic_and_reversed_button = QPushButton("Formula BnR")
        formula_basic_and_reversed_button.pressed.connect(lambda: self.switchWebView(1))
        self.tabButtons.addWidget(formula_basic_and_reversed_button)

    def updateWebView(self, buffer: str):
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
                            self.notes[self.displaying].back_extra += f"\n{line.strip()}"
            elif bl[1].strip() == "model: Basic" or bl[1].strip() == "model: Basic (and reversed card)":
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

            self.webViews[self.displaying].setHtml(self.notes[self.displaying].html())

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
                            equation_symbols.append([split_line[0][2:], split_line[2], split_line[3]])

            note_0 = self.notes[0]
            match len(equation_symbols):
                case 0:
                    note_0_equation_symbol_string = "."
                    note_1_equation_symbol_string = ""
                case 1:
                    note_0_equation_symbol_string = (
                        f", where [{equation_symbols[0][0]}] is [{equation_symbols[0][1]} {equation_symbols[0][2]}]."
                    )
                    note_1_equation_symbol_string = f"{equation_symbols[0][1]}"
                case 2:
                    note_0_equation_symbol_string = ", where\n\n"
                    for pair in equation_symbols:
                        note_0_equation_symbol_string += f" - [{pair[0]}] is [{pair[1]} {pair[2]}]\n"

                    randomised_symbols = random.sample([symbol[1] for symbol in equation_symbols], k=len(equation_symbols))
                    randomised_symbols.insert(len(randomised_symbols) - 1, "and")
                    note_1_equation_symbol_string = " ".join([f"{symbol}" for symbol in randomised_symbols])
                case _:
                    note_0_equation_symbol_string = ", where\n\n"
                    for pair in equation_symbols:
                        note_0_equation_symbol_string += f" - [{pair[0]}] is [{pair[1]} {pair[2]}]\n"

                    randomised_symbols = random.sample([symbol[1] for symbol in equation_symbols], k=len(equation_symbols))
                    randomised_symbols.insert(len(randomised_symbols) - 1, "and")
                    note_1_equation_symbol_string = ", ".join([f"${symbol}$" for symbol in randomised_symbols])
                    note_1_equation_symbol_string = note_1_equation_symbol_string.replace("$and$,", "and").replace("$", "")

            note_0_text = f"{context}[{subject} {symbol}{units}]{equation}{note_0_equation_symbol_string}"
            note_0_text = self.capitalise(note_0_text)

            c = count(1)
            while (match := re.search(r"\[([^\]]+)\]", note_0_text)) is not None:
                note_0_text = note_0_text.replace(f"{match.group(0)}", "{{c" + str(next(c)) + f"::{match.group(0)[1:-1]}" + "}}")

            if note_0.text != note_0_text:
                note_0.text = note_0_text
                self.webViews[0].setHtml(note_0.html())

            note_1 = self.notes[1]
            note_1_front = f"{subject} {symbol}{units}, given {note_1_equation_symbol_string}."
            note_1_front = self.capitalise(note_1_front)

            note_1_back = equation[12:]

            if note_1.front != note_1_front or note_1.back != note_1_back:
                note_1.front = note_1_front
                note_1.back = note_1_back
                self.webViews[1].setHtml(note_1.html())

            self.temp_output_file.seek(0)
            for note in self.notes:
                self.temp_output_file.write(str(note).encode("utf-8"))
