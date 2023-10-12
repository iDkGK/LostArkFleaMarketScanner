import ctypes
import os
import pyautogui
import sys

# import tesserocr
import tempfile
from configparser import (
    ConfigParser,
)
from customtkinter import (
    CTk,
    CTkButton,
    CTkCheckBox,
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

TITLE = "Lost Ark Flea Market Scanner"
ANNOUNCEMENT = """\
作者：iDkGK\n\n\
项目地址：https://github.com/iDkGK/LostArkFleaMarketScanner\n\n\n\n\
本程序禁止用于一切商业用途\n\n\
使用本程序的风险及后果由使用者自行承担\n\n\n\n\
"""

DATA = "data/"
ICON = "lafms.ico"
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
            daemon=True,
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
        Config().load_configs()

    def _create_window(self) -> None:
        set_appearance_mode(Config().get("UI", "theme", fallback="system"))
        self._window = CTk()
        width, height = 640, 360
        xanchor, yanchor = (
            (self._window.winfo_screenwidth() - width) // 2,
            (self._window.winfo_screenheight() - height) // 2,
        )
        self._window.wm_geometry(newGeometry=f"{width}x{height}+{xanchor}+{yanchor}")
        self._window.wm_resizable(width=False, height=False)
        self._window.wm_iconbitmap(bitmap=os.path.join(DATA, ICON))
        self._window.wm_attributes(
            "-alpha", Config().getfloat("UI", "transparency", fallback=1.0)
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
        ctk_textbox = CTkTextbox(master=ctk_tabview_mainpage, state="disabled")
        ctk_textbox.place_configure(relwidth=0.775, relheight=0.875)
        # ----------------------------------------------------------------
        # Button to start collecting data once on `main page` Tab
        ctk_button_once = CTkButton(
            master=ctk_tabview_mainpage,
            text="单次采集",
            command=lambda: Scanner(ctk_textbox).scan_once("test/sample.png"),
        )
        ctk_button_once.place_configure(
            relwidth=0.125,
            relheight=0.1,
            relx=0.1,
            rely=0.9,
        )
        # ----------------------------------------------------------------
        # Button to start auto collecting data on `main page` Tab
        ctk_button_auto = CTkSwitch(
            master=ctk_tabview_mainpage,
            text="自动采集",
            command=lambda: Scanner(ctk_textbox).scan_loop("test/sample.png"),
        )
        ctk_button_auto.place_configure(
            relwidth=0.175,
            relheight=0.1,
            relx=0.3,
            rely=0.9,
        )
        # ----------------------------------------------------------------
        # Button to view collected data on `main page` Tab
        ctk_button_stop = CTkButton(
            master=ctk_tabview_mainpage,
            text="查看结果",
            command=lambda: Scanner(ctk_textbox).view_data(),
        )
        ctk_button_stop.place_configure(
            relwidth=0.125,
            relheight=0.1,
            relx=0.55,
            rely=0.9,
        )
        # ----------------------------------------------------------------
        # Checkbox to test on `main page` Tab
        ctk_checkbox_test = CTkCheckBox(
            master=ctk_tabview_mainpage,
            text="全部启用",
            command=lambda: None,
        )
        ctk_checkbox_test.place_configure(
            relwidth=0.2,
            relheight=0.1,
            relx=0.8,
            rely=0.9,
        )

        # ----------------------------------------------------------------
        # Frame for settings option line on `settings` Tab
        # `ctk_frames_settings`: list of list of CTkFrame and times-used
        ctk_frames_settings_used_times: dict[CTkFrame, int] = {}
        for rely_thousandths in range(0, 8):
            ctk_frame_settings = CTkFrame(master=ctk_tabview_settings)
            ctk_frame_settings.place_configure(
                relwidth=1.0,
                relheight=0.1,
                relx=0.0,
                rely=rely_thousandths / 8.0,
            )
            ctk_frames_settings_used_times[ctk_frame_settings] = 0

        def get_available_frame_settings() -> tuple[CTkFrame, int]:
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
            rely=0.1,
        )
        # ----------------------------------------------------------------
        # Slider to change transparency on `settings` Tab
        ctk_slider = CTkSlider(
            master=ctk_frame_settings,
            command=lambda value: Config().change_transparency(
                self._window,
                value,
            ),
        )
        ctk_slider.set(Config().getfloat("UI", "transparency", fallback=1.0))
        ctk_slider.place_configure(
            relwidth=0.2,
            relheight=0.8,
            relx=offsetx + 0.2,
            rely=0.1,
        )

        # ----------------------------------------------------------------
        # Label for theme Segmented Button on `settings` Tab
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
            rely=0.1,
        )
        # ----------------------------------------------------------------
        # Segmented Button to change theme on `settings` Tab
        ctk_slider = CTkSegmentedButton(
            master=ctk_frame_settings,
            values=["明亮", "灰暗", "自动"],
            command=lambda value: Config().change_theme(value),
        )
        ctk_slider.set(
            {
                "light": "明亮",
                "dark": "灰暗",
                "system": "自动",
            }.get(Config().get("UI", "theme", fallback="system"), "自动")
        )
        ctk_slider.place_configure(
            relwidth=0.2,
            relheight=0.8,
            relx=offsetx + 0.2,
            rely=0.1,
        )
        # ----------------------------------------------------------------
        # Label for announcement on `settings` Tab
        ctk_label_announcement = CTkLabel(
            master=ctk_tabview_aboutpage,
            text=ANNOUNCEMENT,
        )
        ctk_label_announcement.place_configure(
            relwidth=1.0,
            relheight=1.0,
            relx=0.0,
            rely=0.0,
        )

    def run(self) -> None:
        self._window.update()
        self._window.mainloop()
        Config().save_configs()


@cache
class Config(object):
    def __init__(self) -> None:
        temp_dir = tempfile.gettempdir()
        self._config_path = os.path.join(temp_dir, CONFIG)
        self._config_parser = ConfigParser()
        self.get = self._config_parser.get
        self.getboolean = self._config_parser.getboolean
        self.getfloat = self._config_parser.getfloat
        self.getint = self._config_parser.getint

    def load_configs(self) -> None:
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
        if not os.path.exists(self._config_path):
            with open(self._config_path, "w") as config_file:
                default_config_parser.write(config_file)
        self._config_parser.read(self._config_path)

    def save_configs(self) -> None:
        if getattr(self, "_config_path", None) is not None:
            with open(self._config_path, "w") as config_file:
                self._config_parser.write(config_file)

    def change_transparency(self, window: CTk, value: float):
        transparency = value if value > 0.1 else 0.1
        window.wm_attributes("-alpha", transparency)
        self._config_parser["UI"]["transparency"] = str(transparency)

    def change_theme(self, value: str):
        theme = {
            "明亮": "light",
            "灰暗": "dark",
            "自动": "system",
        }.get(value, "system")
        set_appearance_mode(theme)
        self._config_parser["UI"]["theme"] = theme


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
        if self._work_lock.acquire(blocking=False):
            while self._work_event.is_set():
                self._scan(image_path)
            self._work_lock.release()

    @threaded
    def view_data(self) -> None:
        """TODO: Implement this method for data viewing."""

    def _scan(self, image_path: str) -> None:
        """TODO: Implement this method for data collecting."""
        # result = tesserocr.file_to_text(filename=image_path, path=TESSEROCRDATA)
        result = "TEST DATA \n HELLO WORLD\n123456abcd"
        self._ctk_textbox.configure(state="normal")
        self._ctk_textbox.insert(index="end", text=image_path)
        self._ctk_textbox.insert(index="end", text=result)
        if self._ctk_textbox.yview()[1] > 0.9:
            self._ctk_textbox.see("end")
        self._ctk_textbox.configure(state="disabled")
        print(image_path)
        print(result)


if __name__ == "__main__":
    Program().run()
