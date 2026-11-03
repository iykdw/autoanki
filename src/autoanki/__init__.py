import sqlite3
import sys

from PySide6.QtWidgets import QApplication

from autoanki.ui import MainWindow


def main() -> None:
    with sqlite3.connect("notes.db") as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS buffers (id INTEGER, buffer TEXT, type TEXT, deck TEXT, PRIMARY KEY(id AUTOINCREMENT))""")
        c.execute(
            """CREATE TABLE IF NOT EXISTS basic(nid INTEGER CHECK(nid > 0) PRIMARY KEY, deck TEXT, tags TEXT, front TEXT, back TEXT, i INTEGER NOT NULL, buffer_id INTEGER NOT NULL, FOREIGN KEY(buffer_id) REFERENCES buffers(id))"""
        )
        c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS basic_buf_i ON basic(i, buffer_id)""")
        c.execute(
            """CREATE TABLE IF NOT EXISTS basicandreversed(nid INTEGER PRIMARY KEY CHECK(nid > 0), deck TEXT, tags TEXT, front TEXT, back TEXT, i INTEGER NOT NULL, buffer_id INTEGER NOT NULL, FOREIGN KEY(buffer_id) REFERENCES buffers(id))"""
        )
        c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS bnr_buf_i ON basicandreversed(i, buffer_id)""")
        c.execute(
            """CREATE TABLE IF NOT EXISTS cloze(nid INTEGER PRIMARY KEY CHECK(nid>0), deck TEXT, tags TEXT, text TEXT, back_extra TEXT, i INTEGER NOT NULL, buffer_id INTEGER NOT NULL, FOREIGN KEY (buffer_id) REFERENCES buffers(id))"""
        )
        c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS cloze_buf_i ON cloze(i, buffer_id)""")
        # res = c.execute("""SELECT buffer FROM buffers""").fetchall()
        # for re in res:
        #    print(re)
        #    print()
    conn.close()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
