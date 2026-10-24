import sys

from PySide6.QtWidgets import QApplication, QComboBox, QMainWindow, QPushButton, QVBoxLayout, QWidget

from autoanki.note_generators import Definition, Equation, MathsIdentity, SingleBasic


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MainWindow")

        self.note_generators = {"Basic Note": SingleBasic, "Maths Identity": MathsIdentity, "Definition": Definition, "Equation": Equation}

        self.note_type = QComboBox()
        for gen in self.note_generators:
            self.note_type.addItem(gen)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.note_type)

        button = QPushButton("Create")
        button.clicked.connect(lambda: self.note_generators[self.note_type.currentText()]().show())

        self.layout.addWidget(button)

        cw = QWidget()
        cw.setLayout(self.layout)
        self.setCentralWidget(cw)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()

    with open("temp.tex", "w") as f:
        f.write("anki-maths-identity")
