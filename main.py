import ctypes
import os
import pyautogui
import sys
import tesserocr
import tempfile
import time
from configparser import (
    ConfigParser,
)
from customtkinter import (
    CTk,
    CTkButton,
    CTkCheckBox,
    CTkEntry,
    CTkFrame,
    CTkLabel,
    CTkProgressBar,
    CTkScrollableFrame,
    CTkSegmentedButton,
    CTkSlider,
    CTkSwitch,
    CTkTabview,
    CTkTextbox,
    set_appearance_mode,
)
from datetime import datetime
from functools import (
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
    Literal,
    Mapping,
)

WINDOW_TITLE = "Lost Ark Flea Market Scanner"
ANNOUNCEMENT = """\
作者：iDkGK\n\n\
项目地址：https://github.com/iDkGK/LostArkFleaMarketScanner\n\n\n\n\
本程序禁止用于一切商业用途\n\n\
使用本程序的风险及后果由使用者自行承担\n\n\n\n\
"""
DATA_PATH = "data/"
ICON_FILE_NAME = "lafms.ico"
CONFIG_FILE_NAME = "lars-config.ini"
DEFAULT_CONFIG_NAME = "defaultconfig.ini"
TESSEROCR_DATA_PATH = "data/"


def threaded(function_or_method: Callable[..., Any]):
    @wraps(function_or_method)
    def wrapper(
        *args: Iterable[Any],
        **kwargs: Mapping[str, Any],
    ):
        Thread(
            target=function_or_method,
            args=args,
            kwargs=kwargs,
            daemon=True,
        ).start()

    return wrapper


class Program(object):
    def __init__(self) -> None:
        # Elevated privileges
        self._elevate_privileges()
        # Create main window
        self._create_window()
        # Load configurations
        self._load_configs()
        # Initialize worker
        self._setup_worker()

    def _elevate_privileges(self) -> None:
        if not ctypes.windll.shell32.IsUserAnAdmin():
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit()

    def _create_window(self) -> None:
        # Main Window
        self._window = CTk()
        # Tabview for Tab switching
        self._ctk_tabview = CTkTabview(master=self._window)
        self._ctk_tabview.place_configure(relwidth=1.0, relheight=1.0)

        # ----------------------------------------------------------------
        # Tabs of Tabview
        self._ctk_tabview_mainpage = self._ctk_tabview.add("主页")
        self._ctk_tabview_settings = self._ctk_tabview.add("设置")
        self._ctk_tabview_aboutpage = self._ctk_tabview.add("关于")

        # ----------------------------------------------------------------
        # Textbox on `main page` Tab
        self._ctk_textbox_log = CTkTextbox(
            master=self._ctk_tabview_mainpage, state="disabled"
        )
        self._ctk_textbox_log.place_configure(relwidth=0.775, relheight=0.85)
        # ----------------------------------------------------------------
        # Scrollable Frame for categories Checkbox on `main page` Tab
        self._ctk_scrollableframe = CTkScrollableFrame(
            master=self._ctk_tabview_mainpage
        )
        self._ctk_scrollableframe.place(
            relwidth=0.2,
            relheight=1.0,
            relx=0.8,
            rely=0.0,
        )
        # ----------------------------------------------------------------
        # Progress Bar for collecting staus on `main page` Tab
        self._ctk_progressbar_status = CTkProgressBar(master=self._ctk_tabview_mainpage)
        self._ctk_progressbar_status.place_configure(
            relwidth=0.775,
            relheight=0.025,
            relx=0.0,
            rely=0.85,
        )
        # ----------------------------------------------------------------
        # Check Box for "All" category on `main page` Tab
        for _ in range(13):
            self._ctk_checkbox_all = CTkCheckBox(
                master=self._ctk_scrollableframe,
                text="启用类别",
            )
            self._ctk_checkbox_all.pack_configure(pady=5)
        # ----------------------------------------------------------------
        # Button to start collecting data once on `main page` Tab
        self._ctk_button_once = CTkButton(
            master=self._ctk_tabview_mainpage,
            text="单次采集",
            command=self.collect_once,
        )
        self._ctk_button_once.place_configure(
            relwidth=0.125,
            relheight=0.1,
            relx=0.075,
            rely=0.9,
        )
        # ----------------------------------------------------------------
        # Button to start auto collecting data on `main page` Tab
        self._ctk_button_auto = CTkSwitch(
            master=self._ctk_tabview_mainpage,
            text="自动采集",
            command=self.collect_auto,
        )
        self._ctk_button_auto.place_configure(
            relwidth=0.175,
            relheight=0.1,
            relx=0.3,
            rely=0.9,
        )
        # ----------------------------------------------------------------
        # Button to view collected data on `main page` Tab
        self._ctk_button_view = CTkButton(
            master=self._ctk_tabview_mainpage,
            text="查看结果",
            command=self.check_result,
        )
        self._ctk_button_view.place_configure(
            relwidth=0.125,
            relheight=0.1,
            relx=0.575,
            rely=0.9,
        )
        # ----------------------------------------------------------------
        # Frame for settings option line on `settings` Tab
        # `ctk_frames_settings`: list of list of CTkFrame and times-used
        ctk_frames_settings_used_times: dict[CTkFrame, int] = {}
        for rely_thousandths in range(0, 8):
            ctk_frame_settings = CTkFrame(master=self._ctk_tabview_settings)
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
        self._ctk_label_slider_transparency = CTkLabel(
            master=ctk_frame_settings,
            text="透明度",
        )
        self._ctk_label_slider_transparency.place_configure(
            relwidth=0.15,
            relheight=0.8,
            relx=offsetx,
            rely=0.1,
        )
        # ----------------------------------------------------------------
        # Slider to change transparency on `settings` Tab
        self._ctk_slider_transparency = CTkSlider(
            master=ctk_frame_settings, command=self.change_transparency
        )
        self._ctk_slider_transparency.place_configure(
            relwidth=0.2,
            relheight=0.8,
            relx=offsetx + 0.15,
            rely=0.1,
        )
        # ----------------------------------------------------------------
        # Label for transparency value on `settings` Tab
        self._ctk_label_transparency_value = CTkLabel(
            master=ctk_frame_settings,
            text="100%",
        )
        self._ctk_label_transparency_value.place_configure(
            relwidth=0.1,
            relheight=0.8,
            relx=offsetx + 0.35,
            rely=0.1,
        )
        # ----------------------------------------------------------------
        # Label for theme Segmented Button on `settings` Tab
        (
            ctk_frame_settings,
            ctk_frame_settings_used_times,
        ) = get_available_frame_settings()
        offsetx = 0.0 if ctk_frame_settings_used_times < 2 else 0.5
        self._ctk_label_segmentedbutton_theme = CTkLabel(
            master=ctk_frame_settings,
            text="主题",
        )
        self._ctk_label_segmentedbutton_theme.place_configure(
            relwidth=0.15,
            relheight=0.8,
            relx=offsetx,
            rely=0.1,
        )
        # ----------------------------------------------------------------
        # Segmented Button to change theme on `settings` Tab
        self._ctk_segmentedbutton_theme = CTkSegmentedButton(
            master=ctk_frame_settings,
            values=["明亮", "灰暗", "自动"],
            command=self.change_theme,
        )
        self._ctk_segmentedbutton_theme.place_configure(
            relwidth=0.3,
            relheight=0.8,
            relx=offsetx + 0.15,
            rely=0.1,
        )
        # ----------------------------------------------------------------
        # Label for interval Slider on `settings` Tab
        (
            ctk_frame_settings,
            ctk_frame_settings_used_times,
        ) = get_available_frame_settings()
        offsetx = 0.0 if ctk_frame_settings_used_times < 2 else 0.5
        self._ctk_label_entry_interval = CTkLabel(
            master=ctk_frame_settings,
            text="采集间隔",
        )
        self._ctk_label_entry_interval.place_configure(
            relwidth=0.15,
            relheight=0.8,
            relx=offsetx,
            rely=0.1,
        )
        # ----------------------------------------------------------------
        # Slider to change data collecting interval on `settings` Tab
        self._ctk_entry_interval = CTkSlider(
            master=ctk_frame_settings, command=self.change_interval
        )
        self._ctk_entry_interval.place_configure(
            relwidth=0.2,
            relheight=0.8,
            relx=offsetx + 0.15,
            rely=0.1,
        )
        # ----------------------------------------------------------------
        # Label for transparency value on `settings` Tab
        self._ctk_label_interval_value = CTkLabel(
            master=ctk_frame_settings,
            text="24小时",
        )
        self._ctk_label_interval_value.place_configure(
            relwidth=0.1,
            relheight=0.8,
            relx=offsetx + 0.35,
            rely=0.1,
        )
        # ----------------------------------------------------------------
        # Label for announcement on `settings` Tab
        self._ctk_label_announcement = CTkLabel(
            master=self._ctk_tabview_aboutpage,
            text=ANNOUNCEMENT,
        )
        self._ctk_label_announcement.place_configure(
            relwidth=1.0,
            relheight=1.0,
            relx=0.0,
            rely=0.0,
        )
        # ----------------------------------------------------------------
        # Label for output Entry on `settings` Tab
        (
            ctk_frame_settings,
            ctk_frame_settings_used_times,
        ) = get_available_frame_settings()
        offsetx = 0.0 if ctk_frame_settings_used_times < 2 else 0.5
        self._ctk_label_output = CTkLabel(
            master=ctk_frame_settings,
            text="存档路径",
        )
        self._ctk_label_output.place_configure(
            relwidth=0.15,
            relheight=0.8,
            relx=offsetx,
            rely=0.1,
        )
        # ----------------------------------------------------------------
        # Entry to save result on `settings` Tab
        self._ctk_entry_output = CTkEntry(master=ctk_frame_settings)
        self._ctk_entry_output.place_configure(
            relwidth=0.2,
            relheight=0.8,
            relx=offsetx + 0.15,
            rely=0.1,
        )
        # ----------------------------------------------------------------
        # Button to confirm output path on `settings` Tab
        self._ctk_button_confirm = CTkButton(
            master=ctk_frame_settings, text="确认", command=self.confirm_output
        )
        self._ctk_button_confirm.place_configure(
            relwidth=0.075,
            relheight=0.8,
            relx=offsetx + 0.375,
            rely=0.1,
        )

    def _load_configs(self) -> None:
        self._config = Config(self._textbox_log)
        self._config.load_configs()
        set_appearance_mode(self._config.get("UI", "theme", fallback="system"))
        # Window
        width, height = 640, 360
        xanchor, yanchor = (
            (self._window.winfo_screenwidth() - width) // 2,
            (self._window.winfo_screenheight() - height) // 2,
        )
        transparency = self._config.getfloat("UI", "transparency", fallback=1.0)
        self._window.wm_attributes("-alpha", transparency)
        self._window.wm_geometry(newGeometry=f"{width}x{height}+{xanchor}+{yanchor}")
        self._window.wm_iconbitmap(bitmap=os.path.join(DATA_PATH, ICON_FILE_NAME))
        # self._window.wm_overrideredirect(True)
        self._window.wm_resizable(width=False, height=False)
        self._window.wm_title(WINDOW_TITLE)

        # Widgets
        self._ctk_progressbar_status.set(0)
        self._ctk_slider_transparency.set(transparency)
        self._ctk_label_transparency_value.configure(
            text=f"{round(transparency * 100)}%"
        )
        self._ctk_segmentedbutton_theme.set(
            {
                "light": "明亮",
                "dark": "灰暗",
                "system": "自动",
            }.get(self._config.get("UI", "theme", fallback="system"), "自动")
        )
        interval = self._config.getint("Worker", "interval")
        delimiter = [600, 900, 1800, 3600, 10800, 43200, 86400].index(interval)
        self._ctk_entry_interval.set((delimiter + 0.5) / 7.0)
        self._ctk_label_interval_value.configure(
            text=f"{round(interval / 60)}分钟"
            if delimiter < 3
            else f"{round(interval / 3600)}小时"
        )
        self._ctk_entry_output.insert("end", self._config.get("Worker", "output"))

    def _setup_worker(self) -> None:
        self._worker = Worker(self._textbox_log)
        self._worker.setup_self(self._ctk_progressbar_status)

    def _post_run(self) -> None:
        self._worker.clean_up()
        self._config.save_configs()

    def _textbox_log(self, text: str) -> None:
        timestamp = str(datetime.now().time())
        print(f"{timestamp}: {text}", end="")
        self._ctk_textbox_log.configure(state="normal")
        self._ctk_textbox_log.insert(index="end", text=f"{timestamp}: {text}")
        self._ctk_textbox_log.see("end")
        self._ctk_textbox_log.configure(state="disabled")

    def run(self) -> None:
        self._window.update()
        self._window.mainloop()
        self._post_run()

    def collect_once(self) -> None:
        self._worker.work_once()

    def collect_auto(self) -> None:
        self._worker.work_loop(self._config.getint("Worker", "interval"))

    def check_result(self) -> None:
        self._worker.view_data()

    def change_transparency(self, value: float) -> None:
        transparency = value if value > 0.1 else 0.1
        self._window.wm_attributes("-alpha", transparency)
        self._ctk_label_transparency_value.configure(text=f"{round(transparency * 100)}%")
        self._config.update_configs("UI", "transparency", str(transparency))

    def change_theme(self, value: str) -> None:
        theme = {
            "明亮": "light",
            "灰暗": "dark",
            "自动": "system",
        }.get(value, "system")
        set_appearance_mode(theme)
        self._config.update_configs("UI", "theme", theme)

    def change_interval(self, value: float) -> None:
        intervals = [600, 900, 1800, 3600, 10800, 43200, 86400]
        for delimiter, interval in enumerate(intervals):
            if (
                delimiter / 7.0 < value < (delimiter + 1) / 7.0
                and self._config.getint("Worker", "interval") != interval
            ):
                self._ctk_label_interval_value.configure(
                    text=f"{round(interval / 60)}分钟"
                    if delimiter < 3
                    else f"{round(interval / 3600)}小时"
                )
                self._config.update_configs("Worker", "interval", str(interval))

    def confirm_output(self) -> None:
        output_path = self._ctk_entry_output.get()
        os.makedirs(output_path, exist_ok=True)
        if os.path.exists(output_path):
            self._config.update_configs("Worker", "output", output_path)


class Config(object):
    def __init__(self, textbox_log: Callable[[str], None]) -> None:
        self._textbox_log = textbox_log
        temp_dir = tempfile.gettempdir()
        self._config_path = os.path.join(temp_dir, CONFIG_FILE_NAME)
        self._config_parser = ConfigParser()
        self.get = self._config_parser.get
        self.getboolean = self._config_parser.getboolean
        self.getfloat = self._config_parser.getfloat
        self.getint = self._config_parser.getint

    def load_configs(self) -> None:
        default_config_path = os.path.join(DATA_PATH, DEFAULT_CONFIG_NAME)
        default_config_parser = ConfigParser()
        if not os.path.exists(default_config_path):
            with open(default_config_path, "w") as default_config_file:
                default_config_parser["UI"] = {}
                default_config_parser["UI"]["theme"] = "system"
                default_config_parser["UI"]["transparency"] = "0.1"
                default_config_parser["Worker"] = {}
                default_config_parser["Worker"]["interval"] = "3600"
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

    def update_configs(self, section: str, option: str, value: str) -> None:
        self._config_parser[section][option] = value


class Worker(object):
    def __init__(self, textbox_log: Callable[[str], None]) -> None:
        self._textbox_log = textbox_log
        self._stop_signals: list[Literal["stop"]] = []
        self._work_event = Event()
        self._work_lock = Lock()

    def setup_self(self, ctk_progressbar_status: CTkProgressBar) -> None:
        self._ctk_progressbar_status = ctk_progressbar_status

    def clean_up(self) -> None:
        self._work_event.clear()
        if self._work_lock.locked():
            self._work_lock.release()

    @threaded
    def work_once(self) -> None:
        if self._work_event.is_set():
            return
        if self._work_lock.acquire(blocking=False):
            self._collect()
            self._work_lock.release()

    @threaded
    def work_loop(self, interval: int) -> None:
        if self._work_event.is_set():
            self._stop_signals.append("stop")
            self._work_event.clear()
        else:
            self._work_event.set()
        while self._work_event.is_set():
            if self._work_lock.acquire(blocking=False):
                self._collect()
                self._work_lock.release()
            self._update_status(interval)
            time.sleep(interval)
            if len(self._stop_signals) > 0:
                self._stop_signals.pop()
                return

    @threaded
    def view_data(self) -> None:
        """TODO: Implement this method for data viewing."""
        todo = "待实现\n"
        self._textbox_log(todo)

    @threaded
    def _update_status(self, interval: int) -> None:
        time_start = time.time()
        while time.time() - time_start < interval:
            if not self._work_event.is_set():
                break
            self._ctk_progressbar_status.set((time.time() - time_start) / interval)
            time.sleep(1)
        self._ctk_progressbar_status.set(0)

    def _collect(self) -> None:
        """TODO: Implement this method for data collecting."""
        todo = "待实现\n"
        self._textbox_log(todo)
        # result = tesserocr.file_to_text(filename=image_path, path=TESSEROCR_DATA_PATH)
        # self._ctk_textbox.configure(state="normal")
        # self._ctk_textbox.insert(index="end", text=image_path)
        # self._ctk_textbox.insert(index="end", text=result)
        # if self._ctk_textbox.yview()[1] > 0.9:
        #     self._ctk_textbox.see("end")
        # self._ctk_textbox.configure(state="disabled")
        # print(image_path)
        # print(result)


if __name__ == "__main__":
    Program().run()
