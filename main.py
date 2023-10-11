import ctypes
import sys
from customtkinter import (
    CTk,
)

TITLE = "Lost Ark Ragfair Scanner"
ICONPATH = "data/icon.ico"
TESSDATA = "data/"


class Program(object):
    def __init__(self) -> None:
        # Require elevated privileges
        if not ctypes.windll.shell32.IsUserAnAdmin():
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit()
        # Initialize scanner
        self._init_scanner()
        # Create main window
        self._create_window()
        # Create widgets
        self._create_widgets()

    def _init_scanner(self) -> None:
        self._scanner = Scanner()

    def _create_window(self) -> None:
        self._window = CTk()
        width, height = 640, 360
        xanchor, yanchor = (
            (self._window.winfo_screenwidth() - width) // 2,
            (self._window.winfo_screenheight() - height) // 2,
        )
        self._window.wm_geometry(
            newGeometry=f"{width}x{height}+{xanchor-600}+{yanchor+200}"
        )
        self._window.wm_resizable(width=False, height=False)
        # self.window.wm_iconbitmap(bitmap=ICONPATH)
        self._window.wm_attributes("-alpha", 0.1)
        self._window.wm_title(TITLE)

    def _create_widgets(self) -> None:
        pass

    def run(self) -> None:
        self._window.update()
        self._window.mainloop()


class Scanner(object):
    def __init__(self) -> None:
        pass

    def scan(self, image_path: str) -> None:
        pass


if __name__ == "__main__":
    Program().run()
