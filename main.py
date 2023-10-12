import ctypes
import os
import pyautogui
import sys
import tesserocr
import tempfile
from configparser import (
    ConfigParser,
)
from customtkinter import (
    CTk,
    CTkButton,
    CTkFrame,
    CTkLabel,
    CTkSegmentedButton,
    CTkSlider,
    CTkSwitch,
    CTkTabview,
    CTkTextbox,
    set_appearance_mode,
)
from functools import (
    cache,
    wraps,
)
from threading import (
    Event,
    Lock,
    Thread,
)
from typing import (
    Any,
    Callable,
    Iterable,
    Mapping,
)

TITLE = "Lost Ark Ragfair Scanner"

DATA = "data/"
ICON = "icon.ico"
CONFIG = "lars-config.ini"
DEFAULTCONFIG = "defaultconfig.ini"
TESSEROCRDATA = "data/"


def threaded(function_or_method: Callable[..., Any]):
    @wraps(function_or_method)
    def wrapper(
        *args: Iterable[Any],
        **kwargs: Mapping[str, Any],
    ):
        return Thread(
            target=function_or_method,
            args=args,
            kwargs=kwargs,
        ).start()

    return wrapper


class Program(object):
    def __init__(self) -> None:
        # Require elevated privileges
        if not ctypes.windll.shell32.IsUserAnAdmin():
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit()
        # Load configurations
        self._load_configs()
        # Create main window
        self._create_window()
        # Create widgets
        self._create_widgets()

    def _load_configs(self) -> None:
        temp_dir = tempfile.gettempdir()
        config_path = os.path.join(temp_dir, CONFIG)
        default_config_path = os.path.join(DATA, DEFAULTCONFIG)
        default_config_parser = ConfigParser()
        if not os.path.exists(default_config_path):
            with open(default_config_path, "w") as default_config_file:
                default_config_parser["UI"] = {}
                default_config_parser["UI"]["theme"] = "system"
                default_config_parser["UI"]["transparency"] = "0.1"
                default_config_parser["Scanner"] = {}
                default_config_parser.write(default_config_file)
        else:
            default_config_parser.read(default_config_path)
        if not os.path.exists(config_path):
            with open(config_path, "w") as config_file:
                default_config_parser.write(config_file)
        self._config_parser = ConfigParser()
        self._config_parser.read(config_path)

    def _create_window(self) -> None:
        set_appearance_mode(self._config_parser.get("UI", "theme"))
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
        self._window.wm_attributes(
            "-alpha", self._config_parser.getfloat("UI", "transparency")
        )
        self._window.wm_title(TITLE)

    def _create_widgets(self) -> None:
        # Tabview for Tab switching
        ctk_tabview = CTkTabview(master=self._window)
        ctk_tabview.place_configure(relwidth=1.0, relheight=1.0)

        # ----------------------------------------------------------------
        # Tabs of Tabview
        ctk_tabview_mainpage = ctk_tabview.add("主页")
        ctk_tabview_settings = ctk_tabview.add("设置")
        ctk_tabview_aboutpage = ctk_tabview.add("关于")

        # ----------------------------------------------------------------
        # Textbox on `main page` Tab
        ctk_textbox = CTkTextbox(master=ctk_tabview_mainpage)
        ctk_textbox.place_configure(relwidth=1.0, relheight=0.875)
        # Button to start collecting data once on `main page` Tab
        ctk_button = CTkButton(
            master=ctk_tabview_mainpage,
            text="单次采集",
            command=lambda: Scanner(ctk_textbox).scan_once("test/sample.png"),
        )
        ctk_button.place_configure(
            relwidth=0.125,
            relheight=0.1,
            relx=0.2,
            rely=0.9,
        )
        # Button to start auto collecting data on `main page` Tab
        ctk_button = CTkSwitch(
            master=ctk_tabview_mainpage,
            text="自动采集",
            command=lambda: Scanner(ctk_textbox).scan_loop("test/sample.png"),
        )
        ctk_button.place_configure(
            relwidth=0.175,
            relheight=0.1,
            relx=0.4,
            rely=0.9,
        )
        # Button to stop collecting data on `main page` Tab
        ctk_button = CTkButton(
            master=ctk_tabview_mainpage,
            text="查看结果",
            command=lambda: Scanner(ctk_textbox).view_data(),
        )
        ctk_button.place_configure(
            relwidth=0.125,
            relheight=0.1,
            relx=0.65,
            rely=0.9,
        )

        # ----------------------------------------------------------------
        # Frame for settings option line on `settings` Tab
        # `ctk_frames_settings`: list of list of CTkFrame and times-used
        ctk_frames_settings_used_times: dict[CTkFrame, int] = {}
        for rely_thousandths in range(0, 1000, 125):
            ctk_frame_settings = CTkFrame(master=ctk_tabview_settings)
            ctk_frame_settings.place_configure(
                relwidth=1.0,
                relheight=0.1,
                relx=0.0,
                rely=(rely_thousandths + 25) / 1000.0,
            )
            ctk_frames_settings_used_times[ctk_frame_settings] = 0

        def get_available_frame_settings():
            for ctk_frame_settings in ctk_frames_settings_used_times:
                if ctk_frames_settings_used_times[ctk_frame_settings] < 2:
                    ctk_frames_settings_used_times[ctk_frame_settings] += 1
                    return (
                        ctk_frame_settings,
                        ctk_frames_settings_used_times[ctk_frame_settings],
                    )
            else:
                raise Exception("no available frames on settings page")

        # ----------------------------------------------------------------
        # Label for transparency Slider on `settings` Tab
        # Slider to change transparency on `settings` Tab
        (
            ctk_frame_settings,
            ctk_frame_settings_used_times,
        ) = get_available_frame_settings()
        offsetx = 0.0 if ctk_frame_settings_used_times < 2 else 0.5
        ctk_label_slider = CTkLabel(
            master=ctk_frame_settings,
            text="透明度",
        )
        ctk_label_slider.place_configure(
            relwidth=0.15,
            relheight=0.8,
            relx=offsetx + 0.05,
            rely=0.0,
        )
        ctk_slider = CTkSlider(
            master=ctk_frame_settings,
            command=lambda value: self._window.wm_attributes(
                "-alpha", value if value > 0.1 else 0.1
            ),
        )
        ctk_slider.set(self._config_parser.getfloat("UI", "transparency"))
        ctk_slider.place_configure(
            relwidth=0.2,
            relheight=0.8,
            relx=offsetx + 0.2,
            rely=0.0,
        )

        # ----------------------------------------------------------------
        # Label for theme Segmented Button on `settings` Tab
        # Segmented Button to change theme on `settings` Tab
        (
            ctk_frame_settings,
            ctk_frame_settings_used_times,
        ) = get_available_frame_settings()
        offsetx = 0.0 if ctk_frame_settings_used_times < 2 else 0.5
        ctk_label_slider = CTkLabel(
            master=ctk_frame_settings,
            text="主题",
        )
        ctk_label_slider.place_configure(
            relwidth=0.15,
            relheight=0.8,
            relx=offsetx + 0.05,
            rely=0.0,
        )
        ctk_slider = CTkSegmentedButton(
            master=ctk_frame_settings,
            values=["明亮", "灰暗", "自动"],
            command=lambda value: set_appearance_mode(
                "light" if value == "明亮" else "dark" if value == "灰暗" else "system"
            ),
        )
        ctk_slider.set(
            "明亮"
            if (theme := self._config_parser.get("UI", "theme")) == "light"
            else "灰暗"
            if theme == "dark"
            else "自动"
        )
        ctk_slider.place_configure(
            relwidth=0.2,
            relheight=0.8,
            relx=offsetx + 0.2,
            rely=0.0,
        )

    def run(self) -> None:
        self._window.update()
        self._window.mainloop()


@cache
class Scanner(object):
    def __init__(self, ctk_textbox: CTkTextbox) -> None:
        self._ctk_textbox = ctk_textbox
        self._work_event = Event()
        self._work_lock = Lock()

    @threaded
    def scan_once(self, image_path: str) -> None:
        if self._work_lock.acquire(blocking=False):
            self._scan(image_path)
            self._work_lock.release()

    @threaded
    def scan_loop(self, image_path: str) -> None:
        if self._work_event.is_set():
            self._work_event.clear()
        else:
            self._work_event.set()
        if self._work_lock.acquire():
            while self._work_event.is_set():
                self._scan(image_path)
            self._work_lock.release()

    @threaded
    def view_data(self) -> None:
        """TODO: Implement this method for data collecting."""
        pass

    def _scan(self, image_path: str) -> None:
        """TODO: Implement this method for data collecting."""
        # result = tesserocr.file_to_text(filename=image_path, path=TESSEROCRDATA)
        # self._ctk_textbox.insert(index="end", text=image_path)
        # self._ctk_textbox.insert(index="end", text=result)
        # self._ctk_textbox.see("end")
        # print(image_path)
        # print(result)


if __name__ == "__main__":
    Program().run()
