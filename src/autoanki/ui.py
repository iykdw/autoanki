import sqlite3
from inspect import currentframe, getframeinfo

from PySide6.QtWidgets import (
    QComboBox,
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


class Buffer(QListWidgetItem):
    def __init__(self, id: int, buffer: str, listview: QListWidget) -> None:
        super().__init__(buffer, listview)
        self.id = id


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
            lambda: EditCardsUI(str(self.decks.currentText())).show()
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


class EditCardsUI(QWidget):
    def __init__(self, deck: str) -> None:
        super().__init__()
        print(f"{getframeinfo(currentframe()).lineno} hello")
        self.setWindowTitle("Edit Cards")
        self.resize(600, 400)
        self.deck = deck

        self.layout: QVBoxLayout = QVBoxLayout()

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search here")
        self.search_bar.textEdited.connect(self.update_search)
        self.layout.addWidget(self.search_bar)

        self.results = QListWidget()
        self.layout.addWidget(self.results)
        self.update_search("")

        self.setLayout(self.layout)

        self.show()
        self.setWindowFlags()

    def update_search(self, text: str) -> None:
        print(f"{getframeinfo(currentframe()).lineno} {text=}")
        with sqlite3.connect("notes.db") as conn:
            c = conn.cursor()
            buffers = c.execute(
                """SELECT * FROM buffers WHERE deck = ?""", (self.deck,)
            ).fetchall()
        conn.close()

        if not text:
            results = [(buf[0], buf[1]) for buf in buffers[:10]]
        else:
            results = [
                (buf[0], buf[1])
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
            Buffer(buffer[0], buffer[1], self.results)
