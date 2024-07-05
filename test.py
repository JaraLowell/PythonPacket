import tkinter as tk

from serial import Serial
from serial.threaded import ReaderThread, Protocol, LineReader


class SerialReaderProtocolRaw(Protocol):
    tk_listener = None

    def connection_made(self, transport):
        """Called when reader thread is started"""
        if self.tk_listener is None:
            raise Exception("tk_listener must be set before connecting to the socket!")
        print("Connected, ready to receive data...")

    def data_received(self, data):
        """Called with snippets received from the serial port"""
        self.tk_listener.after(0, self.tk_listener.on_data, data.decode())


class SerialReaderProtocolLine(LineReader):
    tk_listener = None
    TERMINATOR = b'\n\r'

    def connection_made(self, transport):
        """Called when reader thread is started"""
        if self.tk_listener is None:
            raise Exception("tk_listener must be set before connecting to the socket!")
        super().connection_made(transport)
        print("Connected, ready to receive data...")

    def handle_line(self, line):
        """New line waiting to be processed"""
        # Execute our callback in tk
        self.tk_listener.after(0, self.tk_listener.on_data, line)


class MainFrame(tk.Frame):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.listbox = tk.Listbox(self)
        self.listbox.pack()
        self.pack()

    def on_data(self, data):
        print("Called from tk Thread:", data)
        self.listbox.insert(tk.END, data)


if __name__ == '__main__':
    app = tk.Tk()

    main_frame = MainFrame()
    # Set listener to our reader
    SerialReaderProtocolLine.tk_listener = main_frame
    # Initiate serial port
    serial_port = Serial("/dev/ttyUSB0")
    # Initiate ReaderThread
    reader = ReaderThread(serial_port, SerialReaderProtocolLine)
    # Start reader
    reader.start()

    app.mainloop()