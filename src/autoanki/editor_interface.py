from pynvim import attach
from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class BufferReadSignal(QObject):
    reload = Signal(str)


class BufferRead(QRunnable):
    def __init__(self, file):
        super().__init__()
        self.signals = BufferReadSignal()

    @Slot()
    def buffer_read(self, last_buffer):
        try:
            nvim = attach("socket", path="/tmp/nvim.sock")
        except:
            return

        this_buffer = ""
        self.buffer = nvim.current.buffer
        for line in range(len(self.buffer)):
            this_buffer += f"{self.buffer[line]}\n"

        buffer = this_buffer.replace("\\\\\n", "\n")

        if last_buffer != this_buffer:
            self.signals.reload.emit(buffer)


class BufferWrite(QRunnable):
    def __init__(self):
        super().__init__()

    @Slot()
    def buffer_write(self, buffer):
        try:
            nvim = attach("socket", path="/tmp/nvim.sock")
        except:
            return

        nvim.current.buffer[:] = buffer.rstrip("\n").split("\n")
