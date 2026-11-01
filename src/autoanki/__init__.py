import sqlite3
import sys

from PySide6.QtWidgets import QApplication

from autoanki.ui import MainWindow


def main() -> None:
    with sqlite3.connect("notes.db") as conn:
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS buffers (id INTEGER, buffer TEXT, subject TEXT, deck TEXT, PRIMARY KEY(id AUTOINCREMENT))"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS basic(nid TEXT PRIMARY KEY, deck TEXT, tags TEXT, front TEXT, back TEXT, buffer_id INTEGER, FOREIGN KEY(buffer_id) REFERENCES buffers(id))"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS cloze(nid TEXT PRIMARY KEY, deck TEXT, tags TEXT, text TEXT, back_extra TEXT, buffer_id INTEGER, FOREIGN KEY (buffer_id) REFERENCES buffers(id))"""
        )
    conn.close()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
