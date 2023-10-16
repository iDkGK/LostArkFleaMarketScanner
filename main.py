import ctypes
import os
import pyautogui  # type: ignore
import sys
import tesserocr  # type: ignore
import tempfile
import time
from configparser import (
    ConfigParser,
)
from customtkinter import (  # type: ignore
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
from datetime import (
    datetime,
)
from functools import (
    wraps,
)
from queue import (
    Queue,
)
from threading import (
    Event,
    Lock,
    Thread,
)
from typing import (
    overload,
    Any,
    Callable,
    Iterable,
    Literal,
    Mapping,
    Union,
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

THREAD_STOP_SIGNALS: list[Literal["stop"]] = []


@overload
def threaded() -> Callable[..., Callable[..., Any]]:
    ...


@overload
def threaded(event: Event) -> Callable[..., Callable[..., Any]]:
    ...


@overload
def threaded(event: None) -> Callable[..., Callable[..., Any]]:
    ...


def threaded(event: Union[Event, None] = None) -> Callable[..., Callable[..., Any]]:
    def decorator(function_or_method: Callable[..., Any]):
        @wraps(function_or_method)
        def wrapper(
            *args: Iterable[Any],
            **kwargs: Mapping[str, Any],
        ):
            if not event is None and not event.is_set():
                return
            Thread(
                target=function_or_method,
                args=args,
                kwargs=kwargs,
                daemon=True,
            ).start()

        return wrapper

    return decorator


@overload
def threaded_loop() -> Callable[..., Callable[..., Any]]:
    ...


@overload
def threaded_loop(event: Event) -> Callable[..., Callable[..., Any]]:
    ...


@overload
def threaded_loop(event: None) -> Callable[..., Callable[..., Event]]:
    ...


def threaded_loop(
    event: Union[Event, None] = None
) -> Callable[..., Callable[..., Union[Any, Event]]]:
    def decorator(function_or_method: Callable[..., Any]):
        @wraps(function_or_method)
        def wrapper(
            *args: Iterable[Any],
            **kwargs: Mapping[str, Any],
        ):
            if not event is None:
                if event.is_set():
                    event.clear()
                else:
                    event.set()
                if event.is_set():
                    return

                def task():
                    next_time = interval + time.time()
                    assert not event is None
                    while not event.wait(next_time - time.time()):
                        next_time += interval
                        function_or_method(*args, **kwargs)

                interval = float(kwargs.get("interval"))
                Thread(
                    target=function_or_method,
                    args=args,
                    kwargs=kwargs,
                    daemon=True,
                ).start()
                Thread(
                    target=task,
                    daemon=True,
                ).start()
            else:

                def task():
                    next_time = interval + time.time()
                    while not task_event.wait(next_time - time.time()):
                        next_time += interval
                        function_or_method(*args, **kwargs)

                task_event = Event()
                interval = float(kwargs.get("interval"))
                Thread(
                    target=function_or_method,
                    args=args,
                    kwargs=kwargs,
                    daemon=True,
                ).start()
                Thread(
                    target=task,
                    daemon=True,
                ).start()
                return task_event

        return wrapper

    return decorator


class Program(object):
    _work_event = Event()
    _work_lock = Lock()

    def __init__(self) -> None:
        # Elevated privileges
        self._elevate_privileges()
        # Create main window
        self._create_window()
        # Load configurations
        self._load_configs()
        # Setup logger util
        self._setup_logger()
        # Initialize worker
        self._setup_worker()

    def _elevate_privileges(self) -> None:
        if not ctypes.windll.shell32.IsUserAnAdmin():
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit()

        self._update_display_event = threaded_loop(None)(
            lambda **_: ctypes.windll.kernel32.SetThreadExecutionState(0x00000002)
        )(interval=1)

    def _create_window(self) -> None:
        self._ctk_window = CTk()
        self._ctk_tabview = CTkTabview(master=self._ctk_window)
        self._ctk_tabview.place_configure(relwidth=1.0, relheight=1.0)
        self._ctk_tabview_mainpage = self._ctk_tabview.add("主页")
        self._ctk_tabview_settings = self._ctk_tabview.add("设置")
        self._ctk_tabview_aboutpage = self._ctk_tabview.add("关于")
        self._ctk_textbox_log = CTkTextbox(
            master=self._ctk_tabview_mainpage, state="disabled"
        )
        self._ctk_textbox_log.place_configure(relwidth=0.775, relheight=0.85)
        self._ctk_scrollableframe = CTkScrollableFrame(
            master=self._ctk_tabview_mainpage
        )
        self._ctk_scrollableframe.place(
            relwidth=0.2,
            relheight=1.0,
            relx=0.8,
            rely=0.0,
        )
        self._ctk_progressbar_worker = CTkProgressBar(master=self._ctk_tabview_mainpage)
        self._ctk_progressbar_worker.place_configure(
            relwidth=0.675,
            relheight=0.02,
            relx=0.0,
            rely=0.86,
        )
        self._ctk_label_countdown = CTkLabel(
            master=self._ctk_tabview_mainpage, text="00:00:00"
        )
        self._ctk_label_countdown.place_configure(
            relwidth=0.1,
            relheight=0.04,
            relx=0.675,
            rely=0.85,
        )
        for _ in range(13):
            self._ctk_checkbox_all = CTkCheckBox(
                master=self._ctk_scrollableframe,
                text="启用类别",
            )
            self._ctk_checkbox_all.pack_configure(pady=5)
        self._ctk_button_once = CTkButton(
            master=self._ctk_tabview_mainpage,
            text="单次采集",
            command=self._collect_once,
        )
        self._ctk_button_once.place_configure(
            relwidth=0.125,
            relheight=0.1,
            relx=0.075,
            rely=0.9,
        )
        self._ctk_swtich_auto = CTkSwitch(
            master=self._ctk_tabview_mainpage,
            text="定期采集",
            command=self._collect_auto,
        )
        self._ctk_swtich_auto.place_configure(
            relwidth=0.175,
            relheight=0.1,
            relx=0.3,
            rely=0.9,
        )
        self._ctk_button_view = CTkButton(
            master=self._ctk_tabview_mainpage,
            text="查看存档",
            command=self._check_result,
        )
        self._ctk_button_view.place_configure(
            relwidth=0.125,
            relheight=0.1,
            relx=0.575,
            rely=0.9,
        )
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
            relheight=0.6,
            relx=offsetx,
            rely=0.2,
        )
        self._ctk_slider_transparency = CTkSlider(
            master=ctk_frame_settings, command=self._change_transparency
        )
        self._ctk_slider_transparency.place_configure(
            relwidth=0.2,
            relheight=0.6,
            relx=offsetx + 0.15,
            rely=0.2,
        )
        self._ctk_label_transparency_value = CTkLabel(
            master=ctk_frame_settings,
            text="100%",
        )
        self._ctk_label_transparency_value.place_configure(
            relwidth=0.1,
            relheight=0.6,
            relx=offsetx + 0.35,
            rely=0.2,
        )
        (
            ctk_frame_settings,
            ctk_frame_settings_used_times,
        ) = get_available_frame_settings()
        offsetx = 0.0 if ctk_frame_settings_used_times < 2 else 0.5
        self._ctk_label_segmentedbutton_theme = CTkLabel(
            master=ctk_frame_settings,
            text="主题设置",
        )
        self._ctk_label_segmentedbutton_theme.place_configure(
            relwidth=0.15,
            relheight=0.6,
            relx=offsetx,
            rely=0.2,
        )
        self._ctk_segmentedbutton_theme = CTkSegmentedButton(
            master=ctk_frame_settings,
            values=["明亮", "灰暗", "自动"],
            command=self._change_theme,
        )
        self._ctk_segmentedbutton_theme.place_configure(
            relwidth=0.3,
            relheight=0.8,
            relx=offsetx + 0.15,
            rely=0.1,
        )
        (
            ctk_frame_settings,
            ctk_frame_settings_used_times,
        ) = get_available_frame_settings()
        offsetx = 0.0 if ctk_frame_settings_used_times < 2 else 0.5
        self._ctk_label_slider_interval = CTkLabel(
            master=ctk_frame_settings,
            text="采集周期",
        )
        self._ctk_label_slider_interval.place_configure(
            relwidth=0.15,
            relheight=0.6,
            relx=offsetx,
            rely=0.2,
        )
        self._ctk_slider_interval = CTkSlider(
            master=ctk_frame_settings, command=self._change_interval
        )
        self._ctk_slider_interval.place_configure(
            relwidth=0.2,
            relheight=0.6,
            relx=offsetx + 0.15,
            rely=0.2,
        )
        self._ctk_label_interval_value = CTkLabel(
            master=ctk_frame_settings,
            text="24小时",
        )
        self._ctk_label_interval_value.place_configure(
            relwidth=0.1,
            relheight=0.6,
            relx=offsetx + 0.35,
            rely=0.2,
        )
        (
            ctk_frame_settings,
            ctk_frame_settings_used_times,
        ) = get_available_frame_settings()
        offsetx = 0.0 if ctk_frame_settings_used_times < 2 else 0.5
        self._ctk_label_entry_archive = CTkLabel(
            master=ctk_frame_settings,
            text="存档路径",
        )
        self._ctk_label_entry_archive.place_configure(
            relwidth=0.15,
            relheight=0.6,
            relx=offsetx,
            rely=0.2,
        )
        self._ctk_entry_archive = CTkEntry(
            master=ctk_frame_settings, placeholder_text="输入存档路径"
        )
        self._ctk_entry_archive.place_configure(
            relwidth=0.2,
            relheight=0.8,
            relx=offsetx + 0.15,
            rely=0.1,
        )
        self._ctk_button_archive = CTkButton(
            master=ctk_frame_settings, text="确认", command=self._confirm_archive
        )
        self._ctk_button_archive.place_configure(
            relwidth=0.075,
            relheight=0.8,
            relx=offsetx + 0.375,
            rely=0.1,
        )
        (
            ctk_frame_settings,
            ctk_frame_settings_used_times,
        ) = get_available_frame_settings()
        offsetx = 0.0 if ctk_frame_settings_used_times < 2 else 0.5
        # TODO: add new widgets here
        (
            ctk_frame_settings,
            ctk_frame_settings_used_times,
        ) = get_available_frame_settings()
        offsetx = 0.0 if ctk_frame_settings_used_times < 2 else 0.5
        self._ctk_label_entry_log = CTkLabel(
            master=ctk_frame_settings,
            text="日志路径",
        )
        self._ctk_label_entry_log.place_configure(
            relwidth=0.15,
            relheight=0.6,
            relx=offsetx,
            rely=0.2,
        )
        self._ctk_entry_log = CTkEntry(
            master=ctk_frame_settings, placeholder_text="输入日志路径"
        )
        self._ctk_entry_log.place_configure(
            relwidth=0.2,
            relheight=0.8,
            relx=offsetx + 0.15,
            rely=0.1,
        )
        self._ctk_button_log = CTkButton(
            master=ctk_frame_settings, text="确认", command=self._confirm_log
        )
        self._ctk_button_log.place_configure(
            relwidth=0.075,
            relheight=0.8,
            relx=offsetx + 0.375,
            rely=0.1,
        )
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

    def _post_run(self) -> None:
        self._update_display_event.set()
        self._save_configs()
        self._notify_logger()
        self._notify_worker()

    def run(self) -> None:
        self._ctk_window.update()
        self._ctk_window.mainloop()
        self._post_run()

    # ----------------------------------------------------------------
    # Callbacks
    def _collect_once(self) -> None:
        self.work_once()

    def _collect_auto(self) -> None:
        self._ctk_button_once.configure(
            state="disabled" if self._work_event.is_set() else "normal"
        )
        self.work_loop(interval=self._config_parser.getint("Worker", "interval"))

    def _check_result(self) -> None:
        self.view_data()

    def _change_transparency(self, value: float) -> None:
        transparency = float(value if value > 0.1 else 0.1)
        self._ctk_window.wm_attributes("-alpha", transparency)
        self._ctk_label_transparency_value.configure(
            text=f"{round(transparency * 100)}%"
        )
        self._update_configs("UI", "transparency", str(transparency))

    def _change_theme(self, value: str) -> None:
        theme = {
            "明亮": "light",
            "灰暗": "dark",
            "自动": "system",
        }.get(value, "system")
        set_appearance_mode(theme)
        self._update_configs("UI", "theme", theme)

    def _change_interval(self, value: float) -> None:
        intervals = [600, 900, 1800, 3600, 10800, 21600, 43200, 86400]
        for delimiter, interval in enumerate(intervals):
            if (
                delimiter / 8.0 < value < (delimiter + 1) / 8.0
                and self._config_parser.getint("Worker", "interval") != interval
            ):
                humanize_interval = (
                    f"{round(interval / 60)}分钟"
                    if delimiter < 3
                    else f"{round(interval / 3600)}小时"
                )
                self._ctk_label_interval_value.configure(text=humanize_interval)
                self._update_configs("Worker", "interval", str(interval))
                self._log_info(f"采集间隔设定为{humanize_interval}，重启“定期采集”后生效")

    def _confirm_archive(self) -> None:
        archive_path = self._ctk_entry_archive.get()
        try:
            os.makedirs(archive_path, exist_ok=True)
            if os.path.exists(archive_path):
                self._update_configs("Worker", "archive", archive_path)
                self._log_info(f"存档路径设定为{os.path.abspath(archive_path)}，重启“定期采集”后生效")
        except:
            self._log_info(f"无法将存档路径设定为{os.path.abspath(archive_path)}")

    def _confirm_log(self) -> None:
        log_path = self._ctk_entry_log.get()
        try:
            os.makedirs(log_path, exist_ok=True)
            if os.path.exists(log_path):
                self._update_configs("Global", "logs", log_path)
                self._log_info(f"日志路径设定为{os.path.abspath(log_path)}，重启程序后生效")
        except:
            self._log_info(f"无法将日志路径设定为{os.path.abspath(log_path)}")

    # ----------------------------------------------------------------
    # Config Manager
    def _load_configs(self) -> None:
        # Load configurations
        temp_dir = tempfile.gettempdir()
        self._config_path = os.path.join(temp_dir, CONFIG_FILE_NAME)
        self._config_parser = ConfigParser()
        default_config_path = os.path.join(DATA_PATH, DEFAULT_CONFIG_NAME)
        default_config_parser = ConfigParser()
        if not os.path.exists(default_config_path):
            with open(default_config_path, "w") as default_config_file:
                default_config_parser["Global"] = {}
                default_config_parser["Global"]["logs"] = "logs"
                default_config_parser["UI"] = {}
                default_config_parser["UI"]["theme"] = "system"
                default_config_parser["UI"]["transparency"] = "1.0"
                default_config_parser["Worker"] = {}
                default_config_parser["Worker"]["archive"] = "result"
                default_config_parser["Worker"]["interval"] = "3600"
                default_config_parser.write(default_config_file)
        else:
            default_config_parser.read(default_config_path)
        if not os.path.exists(self._config_path):
            with open(self._config_path, "w") as config_file:
                default_config_parser.write(config_file)
        self._config_parser.read(self._config_path)
        # Appearance mode
        set_appearance_mode(self._config_parser.get("UI", "theme", fallback="system"))
        # Initialize window
        width, height = 640, 360
        xanchor, yanchor = (
            (self._ctk_window.winfo_screenwidth() - width) // 2,
            (self._ctk_window.winfo_screenheight() - height) // 2,
        )
        transparency = self._config_parser.getfloat("UI", "transparency", fallback=1.0)
        self._ctk_window.wm_attributes("-alpha", transparency)
        self._ctk_window.wm_geometry(
            newGeometry=f"{width}x{height}+{xanchor}+{yanchor}"
        )
        self._ctk_window.wm_iconbitmap(bitmap=os.path.join(DATA_PATH, ICON_FILE_NAME))
        self._ctk_window.wm_resizable(width=False, height=False)
        self._ctk_window.wm_title(WINDOW_TITLE)
        # Initialize widgets
        self._ctk_progressbar_worker.set(0)
        self._ctk_slider_transparency.set(transparency)
        self._ctk_label_transparency_value.configure(
            text=f"{round(transparency * 100)}%"
        )
        self._ctk_segmentedbutton_theme.set(
            {
                "light": "明亮",
                "dark": "灰暗",
                "system": "自动",
            }.get(self._config_parser.get("UI", "theme", fallback="system"), "自动")
        )
        interval = self._config_parser.getint("Worker", "interval")
        delimiter = [600, 900, 1800, 3600, 10800, 21600, 43200, 86400].index(interval)
        self._ctk_slider_interval.set((delimiter + 0.5) / 8.0)
        self._ctk_label_interval_value.configure(
            text=f"{round(interval / 60)}分钟"
            if delimiter < 3
            else f"{round(interval / 3600)}小时"
        )
        self._ctk_entry_archive.insert(
            "end", self._config_parser.get("Worker", "archive")
        )
        self._ctk_entry_log.insert("end", self._config_parser.get("Global", "logs"))

    def _update_configs(self, section: str, option: str, value: str) -> None:
        self._config_parser[section][option] = value

    def _save_configs(self) -> None:
        if not getattr(self, "_config_path", None) is None:
            with open(self._config_path, "w") as config_file:
                self._config_parser.write(config_file)

    # ----------------------------------------------------------------
    # Logger
    def _setup_logger(self) -> None:
        self._log_path = self._config_parser.get("Global", "logs")
        self._logger = open(os.path.join(self._log_path, f"lafms.log"), "w")

    def _notify_logger(self) -> None:
        self._logger.close()

    def _log_success(self, text: str) -> None:
        self._textbox_log(f"[成功]: {text}")

    def _log_info(self, text: str) -> None:
        self._textbox_log(f"[信息]: {text}")

    def _log_warning(self, text: str) -> None:
        self._textbox_log(f"[警告]: {text}")

    def _log_error(self, text: str) -> None:
        self._textbox_log(f"[错误]: {text}")

    def _textbox_log(self, text: str) -> None:
        message = f"{datetime.now().time()} {text}\n"
        print(message, end="")
        self._ctk_textbox_log.configure(state="normal")
        self._ctk_textbox_log.insert(index="end", text=message)
        self._ctk_textbox_log.see("end")
        self._ctk_textbox_log.configure(state="disabled")
        self._logger.write(message)

    # ----------------------------------------------------------------
    # Worker
    def _setup_worker(self) -> None:
        self._work_event.set()

    def _notify_worker(self) -> None:
        self._work_event.clear()
        if self._work_lock.locked():
            self._work_lock.release()

    @threaded(_work_event)
    def work_once(self) -> None:
        if self._work_lock.acquire(blocking=False):
            self._log_info("开始采集数据")
            self._collect()
            self._work_lock.release()

    @threaded_loop(_work_event)
    def work_loop(self, interval: int) -> None:
        if self._work_lock.acquire(blocking=False):
            self._log_info("开始采集数据")
            self._collect()
            self._work_lock.release()
        self._update_countdown(interval)

    @threaded()
    def view_data(self) -> None:
        """TODO: Implement this method for data viewing."""
        todo = "待实现"
        self._log_warning(todo)

    @threaded()
    def _update_countdown(self, interval: int) -> None:
        self._ctk_progressbar_worker.set(0)
        self._ctk_label_countdown.configure(
            text="{:02}:{:02}:{:02}".format(
                round(interval // 3600),
                round(interval % 3600 // 60),
                round(interval % 60),
            )
        )
        next_time = time.time() + interval
        while next_time > time.time() and not self._work_event.wait(1):
            count_down = next_time - time.time()
            self._ctk_progressbar_worker.set(1 - count_down / interval)
            self._ctk_label_countdown.configure(
                text="{:02}:{:02}:{:02}".format(
                    round(count_down // 3600),
                    round(count_down % 3600 // 60),
                    round(count_down % 60),
                )
            )
        self._ctk_progressbar_worker.set(0)
        self._ctk_label_countdown.configure(text="00:00:00")

    def _collect(self) -> None:
        """TODO: Implement this method for data collecting."""
        todo = "待实现"
        self._log_warning(todo)
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
