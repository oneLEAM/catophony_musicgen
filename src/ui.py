import os
import shutil
import threading
from random import choice
from time import sleep
from tkinter import PhotoImage, filedialog
import json
import webbrowser

import customtkinter as ctk
import sounddevice as sd
import soundfile as sf
from PIL import Image
from screeninfo import get_monitors

import src.config
from src.generators.music_generation import MusicGenerator
from src.generators.text_prompt_refiner import TextGenerator


def center_window_to_primary_display(Screen: ctk.CTk | ctk.CTkToplevel, width: int, height: int) -> str:
    """Returns coordinates for a window to be in the center of the primary display"""
    try:
        # Trying to use screeninfo for more accurate result
        primary = None
        for monitor in get_monitors():
            if monitor.is_primary:
                primary = monitor
                break

        if primary:
            # Coordinates for a window to be in the center
            x = primary.x + (primary.width - width) // 2
            y = primary.y + (primary.height - height) // 2

    except Exception as e:
        # Fallback: use winfo (works properly only on systems with one display)
        print(e)
        screen_width = Screen.winfo_screenwidth()
        screen_height = Screen.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

    return f"{width}x{height}+{x}+{y}" # pyright: ignore[reportPossiblyUnboundVariable]


class TerminalWidget(ctk.CTkTextbox):
    """Fake terminal widget for various logs"""
    def __init__(self, master: ctk.CTk, **kwargs):
        super().__init__(master, **kwargs)

        self.configure(
            fg_color="#0D0D0D",
            text_color="#9E7D05",
            font=("Tektur", 14, "normal"),
            state="disabled",
        )

    def log(self, text):
        """Create log in the fake terminal"""
        self.configure(state="normal")

        self.insert("end", f"> {text}\n")

        self.configure(state="disabled")
        self.see("end")


class SettingsWindow(ctk.CTkToplevel):
    """Settings window class"""
    def __init__(self, parent):
        super().__init__(parent)
        
        self.geometry(center_window_to_primary_display(self, 450, 400))
        self.title("Settings")
        self.resizable(False, False)
        self.title_font = ctk.CTkFont(family="Tektur", size=34, weight="bold")
        self.bold_font = ctk.CTkFont(family="Tektur", size=24, weight="bold")
    
    def _detect_models(self) -> list:
        """Returns list of downloaded musicgen models"""
        models = []
        for directory in os.listdir(src.config.MODELS_DIR):
            if "musicgen" == directory.split("-", 1)[0]:
                models.append(directory)
        return models

    def _uninstall_model(self, model_name: str, index: int):
        """Uninstalls target model"""
        shutil.rmtree(os.path.join(src.config.MODELS_DIR, model_name))
        self.buttons[index].configure(text="Uninstalled", state="disabled")

    def _on_option_menu_choice(self, model_name: str):
        """Changes music model in settings.json to chosen one"""
        try:
            with open(os.path.join(src.config.CONFIG_DIR, "settings.json"), "w", encoding="utf-8") as json_file:
                json.dump({"music_model": f"{model_name}"}, json_file, indent=4)
            title = "Notification"
            message = "Changes will take effect after restart"
        except Exception as e:
            print(e)
            title = "Error"
            message = "Error: Something went wrong.\nPerhaps, settings.json is missing"\

        self.popup_window = PopUpWindow(self, title)
        self.popup_window.build_widgets(message)
        self.popup_window.attributes("-topmost", True)

    def build_widgets(self):
        self.settings_label = ctk.CTkLabel(self, text="Settings", font=self.title_font)
        self.settings_label.pack(side="top", anchor="nw", padx=15, pady=(0, 20))
        self.selection_label = ctk.CTkLabel(self, text="Select model:", font=self.bold_font)
        self.selection_label.pack(side="top", anchor="nw", padx=15)
        self.selection_option = ctk.CTkOptionMenu(self, values = src.config.AVAILABLE_MODELS, variable=ctk.StringVar(value=src.config.MUSIC_MODEL), command=self._on_option_menu_choice)
        self.selection_option.pack(side="top", anchor="nw", padx=15, pady=(0, 20))
        self.models_label = ctk.CTkLabel(self, text="Downloaded models:", font=self.bold_font)
        self.models_label.pack(side="top", anchor="nw", padx=15)
        models = self._detect_models()
        self.buttons = []
        
        # Creating widgets for downloaded models
        for i, model in enumerate(models, start=0):
            model_frame = ctk.CTkFrame(self)
            model_frame.pack(side="top", anchor="nw", padx=15, fill="x", pady=(0, 5))
            model_label = ctk.CTkLabel(model_frame, text=model)
            model_label.pack(side="left")
            if model == src.config.MUSIC_MODEL.split("/")[-1] or len(models) == 1:
                state = "disabled"
            else:
                state = "normal"
            model_uninstall_button = ctk.CTkButton(model_frame, text="Uninstall", command=lambda model_name=model, index=i: self._uninstall_model(model_name, index), state=state)
            model_uninstall_button.pack(side="right")
            self.buttons.append(model_uninstall_button)
        
        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.pack(side="bottom", anchor="nw", padx=15, fill="x", pady=10)
        self.version_oneleam_label = ctk.CTkLabel(self.info_frame, text=f"{src.config.APP_VERSION} by oneLEAM")
        self.version_oneleam_label.pack(side="left")
        self.view_github_button = ctk.CTkButton(self.info_frame, text="View on GitHub", command=lambda: webbrowser.open("https://github.com/oneLEAM/catophony_musicgen"))
        self.view_github_button.pack(side="right")
        
        

class LoadingWindow(ctk.CTkToplevel):
    """Loading screen on app start"""
    def __init__(self, parent):
        super().__init__(parent)

        self.geometry(center_window_to_primary_display(self, 300, 150))
        self.resizable(False, False)
        # Removing title bar and window borders
        self.overrideredirect(True)

    def build_widgets(self, message):
        self.loading_label = ctk.CTkLabel(
            self, text="Loading AI Models...\nPlease wait"
        )
        self.loading_label.pack(side="top", pady=10)

        self.note_label = ctk.CTkLabel(
            self,
            text=message,
            font=("Tektur", 14, "normal"),
        )
        self.note_label.pack(side="top", pady=(0, 10))

        self.loading_bar = ctk.CTkProgressBar(self, width=200, mode="indeterminate")
        self.loading_bar.pack(side="top")
        self.loading_bar.start()

class PopUpWindow(ctk.CTkToplevel):
    """Pop up window class"""
    def __init__(self, parent, title: str):
        super().__init__(parent)
        
        self.geometry(center_window_to_primary_display(self, 500, 100))
        self.title(title)
        self.resizable(False, False)
        self.title_font = ctk.CTkFont(family="Tektur", size=30, weight="bold")
    
    def build_widgets(self, message: str):
        self.message_label = ctk.CTkLabel(self, text=message)
        self.message_label.pack(fill="both", expand=True)

class App(ctk.CTk):
    """Main window class"""
    def __init__(self):
        # Getting app's theme
        theme_path = os.path.join(src.config.BASE_DIR, "themes", "main_theme.json")
        ctk.set_default_color_theme(theme_path)

        super().__init__()
        
        # Setting appearance mode
        ctk.set_appearance_mode("dark")

        self.DISABLED_FRAME_COLOR = "#292929"
        self.DISABLED_TEXT_COLOR = "#9E7D05"

        # Loading fonts
        name_font_path = os.path.join(src.config.BASE_DIR, "fonts", "Tektur-Bold.ttf")
        ctk.FontManager.load_font(name_font_path)
        font_path = os.path.join(src.config.BASE_DIR, "fonts", "Tektur-Regular.ttf")
        ctk.FontManager.load_font(font_path)

        # Setting app's icon
        if src.config.OS == "Linux":
            icon_path = os.path.join(src.config.BASE_DIR, "pics", "icon.png")
            icon_image = PhotoImage(file=icon_path)
            self.iconphoto(True, icon_image)
        elif src.config.OS == "Windows":
            icon_path = os.path.join(src.config.BASE_DIR, "pics", "icon.ico")
            self.iconbitmap(icon_path)

        # Getting logo
        logo_path = os.path.join(src.config.BASE_DIR, "pics", "logo.png")
        self.logo = ctk.CTkImage(
            light_image=Image.open(logo_path),
            dark_image=Image.open(logo_path),
            size=(64, 64),
        )

        self.title("Catophony")
        self.geometry(center_window_to_primary_display(self, 515, 880))
        self.minsize(515, 880)

        self.name_font = ctk.CTkFont(family="Tektur", size=44, weight="bold")

        self.withdraw()

        self.loading_screen = LoadingWindow(self)
        models = self._detect_models()
        music_model = src.config.MUSIC_MODEL.split("/")[-1]
        text_model = src.config.TEXT_MODEL.split("/")[-1]
        if music_model in models and text_model in models:
            self.loading_screen.build_widgets("Loading models")
        elif music_model in models and text_model not in models:
            self.loading_screen.build_widgets("Downloading text model")
        elif music_model not in models and text_model not in models:
            self.loading_screen.build_widgets("Downloading text and music models")
        elif music_model not in models and text_model in models:
            self.loading_screen.build_widgets("Downloading music model")

        self.music_data = None
        self._is_playing = False

        threading.Thread(target=self._load_models, daemon=True).start()

    def _detect_models(self) -> list:
        """Returns list of downloaded text and music models"""
        models = []
        for directory in os.listdir(src.config.MODELS_DIR):
            models.append(directory)
        return models

    def _load_models(self):
        """Loading or downloading text and music models"""
        try:
            # Loading or downloading text and music models
            self.music_gen = MusicGenerator()
            self.text_gen = TextGenerator()
        except MemoryError as me:
            self.after(0, self.loading_screen.destroy)
            self.after(0, lambda: self.start_generating_button.configure(state="disabled"))
            self.after(0, lambda title="Error", message="Error: No left space for model.": self._popup(title, message))
            self.after(0, lambda error=me: self.fake_terminal.log(f"Error: No left space for model:\n{error}"))
        except Exception as e:
            self.after(0, self.loading_screen.destroy)
            self.after(0, lambda: self.start_generating_button.configure(state="disabled"))
            self.after(0, lambda title="Error", message="Error: Something went wrong.": self._popup(title, message))
            self.after(0, lambda error=e: self.fake_terminal.log(f"Error: Something went wrong: {error}"))
        
        self.after(0, self._show_main_app)

    def _popup(self, title: str, message: str):
        """Creating a popup window"""
        self.popup_window = PopUpWindow(self, title)
        self.popup_window.build_widgets(message)

    def _show_main_app(self):
        """Deiconifies a withdrawed main window and destroys loading screen"""
        if hasattr(self, "loading_screen") and self.loading_screen:
            self.loading_screen.destroy()

        self.deiconify()

    def build_widgets(self):
        # Frame for logo, app label and settings button
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.pack(side="top", anchor="nw", fill="x")

        self.logo_label = ctk.CTkLabel(self.top_frame, image=self.logo, text="")
        self.logo_label.pack(side="left")
        self.app_label = ctk.CTkLabel(
            self.top_frame, text="Catophony", font=self.name_font
        )
        self.app_label.pack(side="left")
        self.settings_button = ctk.CTkButton(
            self.top_frame, text="settings", command=self.open_settings
        )
        self.settings_button.pack(side="right", anchor="e", padx=15)

        # frame for prompt_label and music_prompt_entry
        self.wandering_frame = ctk.CTkFrame(self)
        self.wandering_frame.pack(side="top", anchor="nw", fill="x")

        self.prompt_label = ctk.CTkLabel(self.wandering_frame, text=">>")
        self.prompt_label.pack(side="left", padx=(15, 0))
        self.music_prompt_entry = ctk.CTkEntry(
            self.wandering_frame, placeholder_text="Enter music description..."
        )
        self.music_prompt_entry.pack(side="left", fill="x", expand=True)
        self.refiner_buttons_frame = ctk.CTkFrame(self)
        self.refiner_buttons_frame.pack(side="top", fill="x", pady=(0, 20))
        self.refine_button = ctk.CTkButton(
            self.refiner_buttons_frame, text="Refine prompt [AI]", command=self._on_refine_click
        )
        self.refine_button.pack(side="left", padx=(15, 0))
        self.translate_button = ctk.CTkButton(
            self.refiner_buttons_frame, text="Translate prompt [AI]", command=self._on_translate_click
        )
        self.translate_button.pack(side="right", padx=(0, 15))

        self.options_frame = ctk.CTkFrame(self)
        self.options_frame.pack(side="top", anchor="nw", fill="x")

        self.duration_label = ctk.CTkLabel(self.options_frame, text="Music duration:")
        self.duration_label.pack(side="top", anchor="nw", padx=15)
        self.duration_slider_frame = ctk.CTkFrame(self)
        self.duration_slider_frame.pack(side="top", anchor="nw", fill="x")
        self.duration_sec_label = ctk.CTkLabel(
            self.duration_slider_frame, text="30s", width=65
        )
        self.duration_sec_label.pack(side="left", padx=(15, 10))
        self.duration_slider = ctk.CTkSlider(
            self.duration_slider_frame,
            from_=10,
            to=300,
            number_of_steps=29,
            command=self._on_slider_move,
        )
        self.duration_slider.pack(side="left", fill="x", expand=True, padx=(0, 15))
        self.duration_slider.set(30)

        self.is_inspiration_checkbox = ctk.CTkCheckBox(
            self, text="Inspiration mode", command=self._on_checkbox_click
        )
        self.is_inspiration_checkbox.pack(
            side="top", anchor="nw", padx=15, pady=(20, 0)
        )

        self.inspiration_options_frame = ctk.CTkFrame(
            self, fg_color=self.DISABLED_FRAME_COLOR, corner_radius=5
        )
        self.inspiration_options_frame.pack(side="top", anchor="nw", padx=10, fill="x")
        self.inspiration_music_label = ctk.CTkLabel(
            self.inspiration_options_frame,
            text="Choose a music file:",
            text_color=self.DISABLED_TEXT_COLOR,
        )
        self.inspiration_music_label.pack(side="top", anchor="nw", padx=5)

        self.inspiration_music_frame = ctk.CTkFrame(
            self.inspiration_options_frame, fg_color=self.DISABLED_FRAME_COLOR
        )
        self.inspiration_music_frame.pack(side="top", anchor="nw", fill="x", padx=5)
        self.inspiration_music_entry = ctk.CTkEntry(
            self.inspiration_music_frame,
            border_color="#F9C80E",
            state="disabled",
            text_color=self.DISABLED_TEXT_COLOR,
        )
        self.inspiration_music_entry.pack(side="left", fill="x", expand=True)
        self.inspiration_music_button = ctk.CTkButton(
            self.inspiration_music_frame,
            text="Choose",
            state="disabled",
            command=self.get_file_path,
        )
        self.inspiration_music_button.pack(side="left")

        self.inspiration_duration_frame = ctk.CTkFrame(
            self.inspiration_options_frame, fg_color=self.DISABLED_FRAME_COLOR
        )
        self.inspiration_duration_frame.pack(side="top", anchor="nw", fill="x", padx=5)
        self.inspiration_duration_label = ctk.CTkLabel(
            self.inspiration_duration_frame,
            text="Inspiration duration:",
            text_color=self.DISABLED_TEXT_COLOR,
        )
        self.inspiration_duration_label.pack(side="top", anchor="nw")
        self.inspiration_duration_slider_frame = ctk.CTkFrame(
            self.inspiration_duration_frame, fg_color=self.DISABLED_FRAME_COLOR
        )
        self.inspiration_duration_slider_frame.pack(
            side="top", anchor="nw", fill="x", pady=(0, 20)
        )
        self.inspiration_duration_sec_label = ctk.CTkLabel(
            self.inspiration_duration_slider_frame,
            text="20s",
            width=65,
            text_color=self.DISABLED_TEXT_COLOR,
        )
        self.inspiration_duration_sec_label.pack(side="left")
        self.inspiration_duration_slider = ctk.CTkSlider(
            self.inspiration_duration_slider_frame,
            from_=5,
            to=20,
            number_of_steps=25,
            command=self._on_inspiration_slider_move,
            state="disabled",
        )
        self.inspiration_duration_slider.pack(side="left", fill="x", expand=True)
        self.inspiration_duration_slider.set(20)

        self.start_generating_button = ctk.CTkButton(
            self, text="Make this music real...", command=self._on_start_click
        )
        self.start_generating_button.pack(
            side="top", fill="x", expand=True, padx=15, pady=(20, 0)
        )

        self.fake_terminal = TerminalWidget(self)
        self.fake_terminal.pack(side="top", padx=15, pady=20, fill="x")
        self.fake_terminal.log("Welcome to Catophony Terminal   /ᐠ > ˕ <マ ₊˚⊹♡")

        self.readiness_label = ctk.CTkLabel(self, text="Music is not ready")
        self.readiness_label.pack(side="top", anchor="nw", padx=15)

        self.audition_frame = ctk.CTkFrame(self)
        self.audition_frame.pack(side="top", anchor="nw", fill="x", pady=(0, 20))
        self.play_button = ctk.CTkButton(
            self.audition_frame,
            text="Play",
            state="disabled",
            command=self._on_play_click,
        )
        self.play_button.pack(side="left", padx=(15, 0))
        self.time_label = ctk.CTkLabel(
            self.audition_frame, text="00:00 / 00:00", width=200
        )
        self.time_label.pack(side="left", expand=True)
        self.reset_button = ctk.CTkButton(
            self.audition_frame,
            text="Reset",
            state="disabled",
            command=self._on_reset_click,
        )
        self.reset_button.pack(side="right", padx=(0, 15))

        self.save_button = ctk.CTkButton(
            self, text="Save", state="disabled", command=self.save_music
        )
        self.save_button.pack(side="top", fill="x", expand=True, padx=15)

    def _on_play_click(self):
        def music_playing_time(sec: int):
            """Counting up time of music playback"""
            seconds = 0
            self._is_playing = True
            while seconds < sec and self._is_playing:
                text = (
                    self._format_time(seconds)
                    + " "
                    + self.time_label.cget("text").split(" ", 1)[1]
                )
                self.after(0, lambda t=text: self.time_label.configure(text=t))
                sleep(1)
                seconds += 1
            text = (
                self._format_time(0)
                + " "
                + self.time_label.cget("text").split(" ", 1)[1]
            )
            self.after(0, lambda t=text: self.time_label.configure(text=t))
            self.play_button.configure(state="normal")

        if self.music_data is None:
            return
        rate = self.music_data[0]  # pyright: ignore[reportOptionalSubscript]
        data = self.music_data[1]  # pyright: ignore[reportOptionalSubscript]
        threading.Thread(
            target=music_playing_time, args=(len(data) / rate,), daemon=True
        ).start()
        # playing generated music
        sd.play(data, samplerate=rate)
        self.play_button.configure(state="disabled")

    def _on_text_ready(self, new_prompt: str, message: str):
        self.music_prompt_entry.delete(0, "end")
        self.music_prompt_entry.insert(0, new_prompt.split("</think>")[-1].replace("\n", "") if "</think>" in new_prompt else new_prompt.replace("\n", ""))
        self.start_generating_button.configure(state="normal")
        self.fake_terminal.log(message)

    def _on_refine_click(self):
        def worker():
            """Generating a text response"""
            refinement = self.text_gen.generate(
                src.config.REFINE_PROMPT,
                self.music_prompt_entry.get()
            )
            self.after(0, lambda refinement=refinement: self._on_text_ready(refinement, "Prompt was successfully refined"))

        try:
            self.fake_terminal.log("Started prompt refinement...")
            self.start_generating_button.configure(state="disabled")
            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            self.fake_terminal.log(f"Something went wrong while refining: {e}")
            self.start_generating_button.configure(state="normal")
            return
    
    def _on_translate_click(self):
        def worker():
            """Generating a text response"""
            translation = self.text_gen.generate(
                src.config.TRANSLATE_PROMPT,
                self.music_prompt_entry.get()
            )
            self.after(0, lambda translation=translation: self._on_text_ready(translation, "Prompt was successfully translated"))

        try:
            self.fake_terminal.log("Started prompt translation...")
            self.start_generating_button.configure(state="disabled")
            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            self.fake_terminal.log(f"Something went wrong while translating: {e}")
            self.start_generating_button.configure(state="normal")
            return

    def _on_reset_click(self):
        self._is_playing = False
        self.play_button.configure(state="normal")
        text = (
            self._format_time(0) + " " + self.time_label.cget("text").split(" ", 1)[1]
        )
        self.time_label.configure(text=text)
        sd.stop()

    def _format_time(self, time_sec: int):
        """Formatting time for the time_label widget"""
        minutes = time_sec // 60
        seconds = time_sec - (minutes * 60)
        return f"{minutes:0>2}:{seconds:0>2}"

    def _on_wave_ready(self, wave: tuple):
        self.music_data = wave
        self.start_generating_button.configure(state="normal")
        self.save_button.configure(state="normal")
        self.play_button.configure(state="normal")
        self.reset_button.configure(state="normal")
        self.readiness_label.configure(text="Music is ready")
        self.time_label.configure(
            text=f"00:00 / {self._format_time(int(len(self.music_data[1]) / self.music_data[0]))}"
        )
        self.fake_terminal.log("The music is ready!")
        self.fake_terminal.log("Listen to it")

    def _on_start_click(self):
        prompt = self.music_prompt_entry.get()
        length = self.duration_slider.get()
        is_inspiration = self.is_inspiration_checkbox.get()
        inspiration_music_path = self.inspiration_music_entry.get()
        beginning_sec = self.inspiration_duration_slider.get()
        if not prompt:
            return
        self.start_generating_button.configure(state="disabled")
        if not is_inspiration:
            inspiration_music_path = ""

        def worker():
            """Generating music"""
            wave = self.music_gen.generate(
                prompt, length, inspiration_music_path, beginning_sec
            )
            self.after(0, self._on_wave_ready, wave)

        self.fake_terminal.log("Initializing model...")
        threading.Thread(target=worker, daemon=True).start()
        threading.Thread(target=self._faking_logs, daemon=True).start()

    def _faking_logs(self):
        """Display a random fake logs"""
        while not self.music_data:
            log = choice(src.config.FAKE_LOGS)
            self.fake_terminal.log(log)
            sleep(3)

    def _on_slider_move(self, value):
        self.duration_sec_label.configure(text=f"{int(value)}s")

    def _on_inspiration_slider_move(self, value):
        self.inspiration_duration_sec_label.configure(text=f"{int(value)}s")

    def get_file_path(self):
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("MP3 files", "*.mp3"),
                ("WAV files", "*.wav"),
                ("OGG files", "*.ogg"),
                ("FLAC files", "*.flac"),
                ("M4A files", "*.m4a"),
                ("AAC files", "*.aac"),
                ("WMA files", "*.wma"),
                ("AIFF files", "*.aiff"),
            ],
            title="Open a music file",
        )

        if file_path:
            self.inspiration_music_entry.delete(0, "end")
            self.inspiration_music_entry.insert(0, file_path)

    def save_music(self):
        self.save_button.configure(state="disabled")
        rate, wave = self.music_data  # pyright: ignore[reportGeneralTypeIssues]
        file_path = filedialog.asksaveasfilename(
            filetypes=[
                ("MP3 files", "*.mp3"),
                ("WAV files", "*.wav"),
                ("FLAC files", "*.flac"),
                ("OGG files", "*.ogg"),
            ]
        )

        if not file_path or file_path.rsplit(".", 1)[-1] not in ["mp3", "wav", "flac", "ogg"]:
            self.save_button.configure(state="normal")
            return

        try:
            sf.write(file_path, wave, rate)
            self.fake_terminal.log(f"Successfully saved to {file_path}")
            self._is_playing = False
            sd.stop()
            self.music_data = None
            self.play_button.configure(state="disabled")
            self.reset_button.configure(state="disabled")
            self.readiness_label.configure(text="Music is not ready")
            self.time_label.configure(text="00:00 / 00:00")
        except Exception as e:
            self.fake_terminal.log(f"Something went wrong while saving: {e}")

    def open_settings(self):
        self.settings_window = SettingsWindow(self)
        self.settings_window.build_widgets()
        self.settings_window.attributes("-topmost", True)

    def _on_checkbox_click(self):
        """Activate or deactivate inspiration section"""
        if self.is_inspiration_checkbox.get():
            self.inspiration_options_frame.configure(fg_color="#1B1B1B")
            self.inspiration_music_frame.configure(fg_color="#1B1B1B")
            self.inspiration_duration_frame.configure(fg_color="#1B1B1B")
            self.inspiration_duration_slider_frame.configure(fg_color="#1B1B1B")

            self.inspiration_music_label.configure(text_color="#F9C80E")
            self.inspiration_duration_label.configure(text_color="#F9C80E")
            self.inspiration_duration_sec_label.configure(text_color="#F9C80E")
            self.inspiration_music_entry.configure(text_color="#F9C80E")

            self.inspiration_music_entry.configure(state="normal")
            self.inspiration_music_button.configure(state="normal")
            self.inspiration_duration_slider.configure(state="normal")

        else:
            self.inspiration_options_frame.configure(fg_color=self.DISABLED_FRAME_COLOR)
            self.inspiration_music_frame.configure(fg_color=self.DISABLED_FRAME_COLOR)
            self.inspiration_duration_frame.configure(
                fg_color=self.DISABLED_FRAME_COLOR
            )
            self.inspiration_duration_slider_frame.configure(
                fg_color=self.DISABLED_FRAME_COLOR
            )

            self.inspiration_music_label.configure(text_color=self.DISABLED_TEXT_COLOR)
            self.inspiration_duration_label.configure(
                text_color=self.DISABLED_TEXT_COLOR
            )
            self.inspiration_duration_sec_label.configure(
                text_color=self.DISABLED_TEXT_COLOR
            )
            self.inspiration_music_entry.configure(text_color=self.DISABLED_TEXT_COLOR)

            self.inspiration_music_entry.configure(state="disabled")
            self.inspiration_music_button.configure(state="disabled")
            self.inspiration_duration_slider.configure(state="disabled")
