import sqlite3

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from thefuzz import process

from autoanki.apy_interface import get_decks
from autoanki.note_generators import Definition, Equation, SingleBasic
from autoanki.notes import Basic, BasicAndReversed, Cloze


class Buffer(QListWidgetItem):
    def __init__(
        self, id: int, buffer: str, buf_type: str, listview: QListWidget
    ) -> None:
        super().__init__(buffer, listview)
        self.id = id
        self.buffer = buffer
        match buf_type:
            case "":
                self.buf_type = SingleBasic
            case "definition":
                self.buf_type = Definition
            case "Equation":
                self.buf_type = Equation


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MainWindow")

        self.note_generators = {
            "Basic Note": SingleBasic,
            "Definition": Definition,
            "Equation": Equation,
        }

        self.decks = QComboBox()
        for deck in get_decks():
            self.decks.addItem(deck)

        self.note_type = QComboBox()
        for gen in self.note_generators:
            self.note_type.addItem(gen)

        self.layout: QVBoxLayout = QVBoxLayout()
        self.layout.addWidget(self.decks)
        self.layout.addWidget(self.note_type)

        self.buttons = QHBoxLayout()

        edit_button = QPushButton("Edit")
        edit_button.clicked.connect(
            lambda: EditNotesUI(str(self.decks.currentText())).show()
        )
        self.buttons.addWidget(edit_button)

        create_button = QPushButton("Create")
        create_button.clicked.connect(
            lambda: self.note_generators[self.note_type.currentText()](
                str(self.decks.currentText())
            ).show()
        )

        self.buttons.addWidget(create_button)

        self.layout.addLayout(self.buttons)

        cw = QWidget()
        cw.setLayout(self.layout)
        self.setCentralWidget(cw)


class EditNotesUI(QWidget):
    def __init__(self, deck: str) -> None:
        super().__init__()
        self.setWindowTitle("Edit Notes")
        self.resize(600, 400)
        self.note_width: int = 500
        self.note_height = 300
        self.deck = deck

        self.layout: QVBoxLayout = QVBoxLayout()
        self.margins: list[int] = [10, 10, 10, 10]  # left, top, right, bottom
        self.layout.setContentsMargins(
            self.margins[0], self.margins[1], self.margins[2], self.margins[3]
        )
        self.spacing = 10
        self.layout.setSpacing(self.spacing)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search here")
        self.search_bar.textEdited.connect(self.update_search)
        self.layout.addWidget(self.search_bar)

        self.results = QListWidget()
        self.results.itemClicked.connect(
            lambda: self.switch_web_view(self.results.currentItem())
        )
        self.results.itemDoubleClicked.connect(
            lambda: self.open_new_buf(self.results.currentItem())
        )
        self.layout.addWidget(self.results)
        self.update_search("")

        self.web_view_grid = QGridLayout()
        self.web_views: list[QWebEngineView] = []
        self.layout.addLayout(self.web_view_grid)

        self.setLayout(self.layout)

    def update_search(self, text: str) -> None:
        with sqlite3.connect("notes.db") as conn:
            c = conn.cursor()
            buffers = c.execute(
                """SELECT * FROM buffers WHERE deck = ?""", (self.deck,)
            ).fetchall()
        conn.close()

        if not text:
            results = [(buf[0], buf[1], buf[2]) for buf in buffers[:10]]
        else:
            results = [
                (buf[0], buf[1], buf[2])
                for buf in buffers
                if buf[1]
                in [
                    val[0]
                    for val in process.extract(
                        text, [buf[1] for buf in buffers], limit=10
                    )
                ]
            ]

        self.results.clear()

        for buffer in results:
            Buffer(buffer[0], buffer[1], buffer[2], self.results)

    def switch_web_view(self, buffer: Buffer) -> None:
        with sqlite3.connect("notes.db") as conn:
            c = conn.cursor()
            notes = [None] * 100
            basics = c.execute(
                """SELECT * FROM basic WHERE buffer_id = ?""", (buffer.id,)
            ).fetchall()

            for basic in basics:
                note = Basic(front=basic[3], back=basic[4])
                note.nid = basic[0]
                note.tags = basic[2]
                notes[basic[5]] = note
            bnrs = c.execute(
                """SELECT * FROM basicandreversed WHERE buffer_id = ?""", (buffer.id,)
            ).fetchall()

            for bnr in bnrs:
                note = BasicAndReversed(front=bnr[3], back=bnr[4])
                note.nid = bnr[0]
                note.tags = bnr[2]
                notes[bnr[5]] = note

            clozes = c.execute(
                """SELECT * FROM cloze WHERE buffer_id = ?""", (buffer.id,)
            ).fetchall()
            for cloze in clozes:
                note = Cloze(text=cloze[3], back_extra=cloze[4])
                note.nid = cloze[0]
                note.tags = cloze[2]
                notes[cloze[5]] = note

            notes = [note for note in notes if note]

        conn.close()

        self.curr_buf_notes = notes
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
            vw = None

        for i, note in enumerate(notes):
            try:
                self.web_views[i] = QWebEngineView()
            except IndexError:
                self.web_views.append(QWebEngineView())

            web_view = self.web_views[i]
            web_view.setHtml(note.html())
            x: int = note_layouts[len(notes)][i][0]
            y: int = note_layouts[len(notes)][i][1]

            web_view.setFixedSize(self.note_width, self.note_height)
            web_view.resize(self.note_width, self.note_height)
            web_view.show()
            if len(note_layouts[len(notes)][i]) > 2:
                x2: int = note_layouts[len(notes)][i][2]
                y2: int = note_layouts[len(notes)][i][3]
                self.web_view_grid.addWidget(web_view, x, y, x2, y2)
            else:
                self.web_view_grid.addWidget(web_view, x, y)

        window_width = (
            (grid_xy[len(notes)][0] * (self.note_width + self.spacing))
            - self.spacing
            + self.margins[0]
            + self.margins[2]
        )
        window_height = (
            (grid_xy[len(notes)][1] * (self.note_height + self.spacing))
            + 50
            + self.margins[1]
            + self.margins[2]
        )
        self.resize(window_width, window_height)

    def open_new_buf(self, buffer: Buffer) -> None:
        buffer.buf_type(
            self.deck, id=buffer.id, buffer=buffer.buffer, notes=self.curr_buf_notes
        ).show()
