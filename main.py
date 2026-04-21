from config import *
from targets import TargetManager
from target_predictor import TargetClamper

import pyautogui
import time
import json
import os
import sys
import cv2
import numpy as np
import mss

IS_MACOS = sys.platform == "darwin"

if IS_MACOS:
    try:
        from Quartz import (
            CGEventSourceKeyState,
            CGEventCreateKeyboardEvent,
            CGEventPost,
            kCGEventSourceStateHIDSystemState,
            kCGKeyboardEventKeycode,
        )

        QUARTZ_AVAILABLE = True
    except ImportError:
        QUARTZ_AVAILABLE = False
else:
    QUARTZ_AVAILABLE = True

CHAR_TO_KEYCODE = {
    "a": 0,
    "s": 1,
    "d": 2,
    "f": 3,
    "h": 4,
    "g": 5,
    "z": 6,
    "x": 7,
    "c": 8,
    "v": 9,
    "b": 11,
    "q": 12,
    "w": 13,
    "e": 14,
    "r": 15,
    "y": 16,
    "t": 17,
    "1": 18,
    "2": 19,
    "3": 20,
    "4": 21,
    "6": 22,
    "5": 23,
    "=": 24,
    "9": 25,
    "7": 26,
    "-": 27,
    "8": 28,
    "0": 29,
    "]": 30,
    "o": 31,
    "u": 32,
    "[": 33,
    "i": 34,
    "p": 35,
    "l": 37,
    "j": 38,
    "'": 39,
    "k": 40,
    ";": 41,
    "\\": 42,
    ",": 43,
    "/": 44,
    "n": 45,
    "m": 46,
    ".": 47,
    " ": 49,
    "`": 50,
    ")": 51,
}

pyautogui.PAUSE = 0


def press_key(key):
    if IS_MACOS and QUARTZ_AVAILABLE:
        keycode = CHAR_TO_KEYCODE.get(key.lower())
        if keycode is not None:
            try:
                down = CGEventCreateKeyboardEvent(None, kCGKeyboardEventKeycode, True)
                up = CGEventCreateKeyboardEvent(None, kCGKeyboardEventKeycode, False)
                if down and up:
                    CGEventSetIntegerValueField(down, kCGKeyboardEventKeycode, keycode)
                    CGEventSetIntegerValueField(up, kCGKeyboardEventKeycode, keycode)
                    CGEventPost(kCGEventSourceStateHIDSystemState, down)
                    CGEventPost(kCGEventSourceStateHIDSystemState, up)
                    return
            except Exception:
                pass
    pyautogui.keyDown(key)
    pyautogui.keyUp(key)


PROFILES_DIR = "profiles"
DEFAULT_DELAY = 100
pressed_keys = set()
prev_key_states = {}

KEYCODE_TO_CHAR = {
    0: "a",
    1: "s",
    2: "d",
    3: "f",
    4: "h",
    5: "g",
    6: "z",
    7: "x",
    8: "c",
    9: "v",
    11: "b",
    12: "q",
    13: "w",
    14: "e",
    15: "r",
    16: "y",
    17: "t",
    18: "1",
    19: "2",
    20: "3",
    21: "4",
    22: "6",
    23: "5",
    24: "=",
    25: "9",
    26: "7",
    27: "-",
    28: "8",
    29: "0",
    30: "]",
    31: "o",
    32: "u",
    33: "[",
    34: "i",
    35: "p",
    37: "l",
    38: "j",
    39: "'",
    40: "k",
    41: ";",
    42: "\\",
    43: ",",
    44: "/",
    45: "n",
    46: "m",
    47: ".",
    49: " ",
    50: "`",
    51: ")",
    123: "left",
    124: "right",
    125: "down",
    126: "up",
}


class TargetDetector:
    def __init__(self):
        self.target_manager = TargetManager()

        self.sct = mss.mss()
        mon = self.sct.monitors[1]
        self.region = {
            "left": int((mon["width"] - CAPTURE_WIDTH) / 2),
            "top": int((mon["height"] - CAPTURE_HEIGHT) / 2),
            "width": CAPTURE_WIDTH,
            "height": CAPTURE_HEIGHT,
        }
        self.detections = []
        self.clamper = TargetClamper()
        self.clamped_pos = None
        self.raw_target_pos = None

    def capture(self):
        img = np.array(self.sct.grab(self.region))
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img

    def detect(self):
        frame = self.capture()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        all_detections = []

        for target_id, target in self.target_manager.get_all().items():
            mask = cv2.inRange(hsv, target.lower_hsv, target.upper_hsv)
            resized = cv2.resize(
                target.template_gray, (target.scaled_w, target.scaled_h)
            )
            result = cv2.matchTemplate(gray, resized, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= target.template_threshold)

            for pt in zip(*locations[::-1]):
                x, y = pt
                roi_mask = mask[y : y + target.scaled_h, x : x + target.scaled_w]
                color_pixels = cv2.countNonZero(roi_mask)
                color_ratio = color_pixels / (target.scaled_w * target.scaled_h)
                score = result[y, x]

                if color_ratio >= target.color_threshold:
                    all_detections.append(
                        {
                            "x": x,
                            "y": y,
                            "w": target.scaled_w,
                            "h": target.scaled_h,
                            "score": score,
                            "color_ratio": color_ratio,
                            "target_id": target_id,
                        }
                    )

        self.detections = self._filter_overlapping(all_detections)

        center_x = PLAYER_OFFSET_X
        center_y = PLAYER_OFFSET_Y
        for det in self.detections:
            target_cx = det["x"] + det["w"] // 2 + TARGET_OFFSET_X
            target_cy = det["y"] + det["h"] // 2 + TARGET_OFFSET_Y
            det["dist_to_center"] = np.sqrt(
                (target_cx - center_x) ** 2 + (target_cy - center_y) ** 2
            )

        self.detections.sort(key=lambda d: d["dist_to_center"])
        return self.detections

    def _filter_overlapping(self, detections):
        if not detections:
            return []
        filtered = []
        for det in detections:
            is_dup = any(
                abs(det["x"] - d["x"]) < 30 and abs(det["y"] - d["y"]) < 30
                for d in filtered
            )
            if not is_dup:
                filtered.append(det)
        return filtered

    def get_closest_target_pos(self):
        return self.clamped_pos

    def get_raw_target_pos(self):
        return self.raw_target_pos

    def update_clamped_pos(self, region_offset):
        self.clamped_pos = self.clamper.update(self.detections, region_offset)
        self.raw_target_pos = self.clamper.get_raw_target_pos(self.detections)


class ProfileManager:
    def __init__(self):
        if not os.path.exists(PROFILES_DIR):
            os.makedirs(PROFILES_DIR)

    def create_profile(self, name):
        profile = {
            "name": name,
            "combos": [
                {
                    "attacks": [{"key": "", "delay": DEFAULT_DELAY}],
                    "hotkey": "z",
                    "auto_aim": True,
                }
            ],
        }
        self.save_profile(name, profile)
        return profile

    def save_profile(self, name, profile):
        filepath = os.path.join(PROFILES_DIR, f"{name}.json")
        with open(filepath, "w") as f:
            json.dump(profile, f, indent=2)

    def load_profile(self, name):
        filepath = os.path.join(PROFILES_DIR, f"{name}.json")
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return json.load(f)
        return None

    def list_profiles(self):
        profiles = []
        for filename in os.listdir(PROFILES_DIR):
            if filename.endswith(".json"):
                profiles.append(filename[:-5])
        return sorted(profiles)

    def delete_profile(self, name):
        filepath = os.path.join(PROFILES_DIR, f"{name}.json")
        if os.path.exists(filepath):
            os.remove(filepath)


class SkillAssistantBot:
    def __init__(self):
        self.running = False
        self.target_detector = TargetDetector()
        self.profile_manager = ProfileManager()

        self.profiles = self.profile_manager.list_profiles()
        if not self.profiles:
            self.profile_manager.create_profile("default")
            self.profiles = ["default"]

        self.current_profile_name = "default"
        self.load_profile("default")

        self.combos_state = {}
        for i in range(len(self.combos)):
            self.combos_state[i] = {
                "pressed": False,
                "idx": 0,
                "next_time": 0,
                "initial_fire": False,
            }

    def load_profile(self, name):
        profile = self.profile_manager.load_profile(name)
        if profile:
            self.current_profile_name = name
            self.combos = profile.get("combos", [])
            self.combos_state = {}
            for i in range(len(self.combos)):
                self.combos_state[i] = {
                    "pressed": False,
                    "idx": 0,
                    "next_time": 0,
                    "initial_fire": False,
                }

    def save_current_profile(self):
        profile = {"name": self.current_profile_name, "combos": self.combos}
        self.profile_manager.save_profile(self.current_profile_name, profile)

    def start(self):
        self.running = True
        for i in range(len(self.combos)):
            self.combos_state[i]["idx"] = 0
            self.combos_state[i]["next_time"] = 0

    def stop(self):
        self.running = False


bot = SkillAssistantBot()


def poll_keyboard():
    global prev_key_states

    for keycode, char in KEYCODE_TO_CHAR.items():
        current = (
            CGEventSourceKeyState(kCGEventSourceStateHIDSystemState, keycode)
            if IS_MACOS
            else False
        )
        prev = prev_key_states.get(keycode, 0)

        if current and not prev:
            if char not in pressed_keys:
                pressed_keys.add(char)
                if bot.running:
                    for i, combo in enumerate(bot.combos):
                        hotkey = combo.get("hotkey", "")
                        if char == hotkey:
                            bot.combos_state[i]["pressed"] = True
                            bot.combos_state[i]["idx"] = 0
                            bot.combos_state[i]["next_time"] = 0
                            bot.combos_state[i]["initial_fire"] = True
        elif not current and prev:
            pressed_keys.discard(char)
            for i, combo in enumerate(bot.combos):
                hotkey = combo.get("hotkey", "")
                if char == hotkey:
                    bot.combos_state[i]["pressed"] = False

        prev_key_states[keycode] = current

    root.after(15, poll_keyboard)


import tkinter as tk
from tkinter import ttk, messagebox

root = tk.Tk()
root.title("SkillAssistant + Auto Aim")
root.geometry("700x750")

main_canvas = tk.Canvas(root)
main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

scrollbar = ttk.Scrollbar(root, orient="vertical", command=main_canvas.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
main_canvas.configure(yscrollcommand=scrollbar.set)

content_frame = tk.Frame(main_canvas)
main_canvas.create_window((0, 0), window=content_frame, anchor="nw")
content_frame.bind(
    "<Configure>", lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
)

profile_var = tk.StringVar()
combo_widgets = {}


def get_combo_preview(combo):
    keys = [a.get("key", "") for a in combo.get("attacks", []) if a.get("key", "")]
    if len(keys) > 5:
        return " -> ".join(keys[:5]) + " ..."
    return " -> ".join(keys) if keys else "(vazio)"


def update_combo_preview(combo_idx):
    if combo_idx < len(bot.combos) and combo_idx in combo_widgets:
        cw = combo_widgets[combo_idx]
        if "preview_label" in cw:
            preview = get_combo_preview(bot.combos[combo_idx])
            cw["preview_label"].config(text=preview)


def update_expand_btn(combo_idx):
    if combo_idx in combo_widgets:
        cw = combo_widgets[combo_idx]
        if "expand_btn" in cw and "expanded" in cw:
            text = "▲" if cw["expanded"].get() else "▼"
            cw["expand_btn"].config(text=text)


def remove_this_combo(combo_idx):
    if len(bot.combos) <= 1:
        messagebox.showwarning("Aviso", "Deve ter pelo menos 1 combo!")
        return
    update_attacks_from_ui()
    bot.combos.pop(combo_idx)
    bot.combos_state.pop(combo_idx, None)
    bot.save_current_profile()
    refresh_ui()


def update_profile_list():
    bot.profiles = bot.profile_manager.list_profiles()
    profile_combo["values"] = bot.profiles


def on_profile_select(event):
    name = profile_var.get()
    if name:
        bot.load_profile(name)
        refresh_ui()


def create_new_profile():
    dialog = tk.Toplevel(root)
    dialog.title("Novo Profile")
    dialog.geometry("300x100")
    dialog.transient(root)
    dialog.grab_set()

    tk.Label(dialog, text="Nome do Profile:").pack(pady=5)
    name_var = tk.StringVar()
    name_entry = tk.Entry(dialog, textvariable=name_var, width=30)
    name_entry.pack(pady=5)
    name_entry.focus()

    def create():
        name = name_var.get().strip()
        if name:
            if name in bot.profile_manager.list_profiles():
                messagebox.showerror("Erro", "Profile já existe!")
                return
            bot.profile_manager.create_profile(name)
            update_profile_list()
            profile_var.set(name)
            bot.load_profile(name)
            refresh_ui()
            dialog.destroy()

    tk.Button(dialog, text="Criar", command=create).pack(pady=5)
    dialog.bind("<Return>", lambda e: create())


def save_profile():
    update_attacks_from_ui()
    bot.save_current_profile()
    messagebox.showinfo("Sucesso", f"Profile '{bot.current_profile_name}' salvo!")


def delete_current_profile():
    name = profile_var.get()
    if name == "default":
        messagebox.showerror("Erro", "Nao pode excluir o profile default!")
        return
    if messagebox.askyesno("Confirmar", f"Excluir profile '{name}'?"):
        bot.profile_manager.delete_profile(name)
        update_profile_list()
        profile_var.set("default")
        bot.load_profile("default")
        refresh_ui()


def update_attacks_from_ui():
    for i, cw in combo_widgets.items():
        if i < len(bot.combos):
            attacks = []
            for key_var, delay_var in cw["entries"]:
                key = key_var.get().strip()
                delay = (
                    int(delay_var.get()) if delay_var.get().isdigit() else DEFAULT_DELAY
                )
                attacks.append({"key": key, "delay": delay})
            if not attacks:
                attacks = [{"key": "", "delay": DEFAULT_DELAY}]
            bot.combos[i]["attacks"] = attacks
            bot.combos[i]["hotkey"] = cw["hotkey_var"].get().strip().lower()
            bot.combos[i]["auto_aim"] = cw["auto_aim_var"].get()


def refresh_ui():
    profile_var.set(bot.current_profile_name)
    for i, cw in combo_widgets.items():
        if "frame" in cw:
            cw["frame"].destroy()
    combo_widgets.clear()
    for i, combo in enumerate(bot.combos):
        create_combo_widget(i, combo)
    main_canvas.update_idletasks()
    main_canvas.configure(scrollregion=main_canvas.bbox("all"))
    for i in range(len(bot.combos)):
        update_combo_preview(i)


def toggle_combo(i):
    cw = combo_widgets.get(i)
    if cw is None:
        return
    if cw["expanded"].get():
        cw["expanded"].set(False)
        cw["list_frame"].pack_forget()
    else:
        cw["expanded"].set(True)
        cw["list_frame"].pack(fill=tk.BOTH, expand=True, pady=5)
    update_expand_btn(i)
    main_canvas.update_idletasks()
    main_canvas.configure(scrollregion=main_canvas.bbox("all"))


def create_combo_widget(i, combo):
    frame = ttk.LabelFrame(content_frame, text=f"Combo {i + 1}", padding="10")
    frame.pack(fill=tk.X, padx=10, pady=5)

    expanded = tk.BooleanVar(value=False)
    top_frame = tk.Frame(frame)
    top_frame.pack(fill=tk.X)

    preview = get_combo_preview(combo)
    hotkey_var = tk.StringVar(value=combo.get("hotkey", ""))

    preview_label = tk.Label(
        top_frame, text=preview, font=("Arial", 9), fg="blue", width=30
    )
    preview_label.pack(side=tk.LEFT, padx=5)

    tk.Label(top_frame, text="Hotkey:").pack(side=tk.LEFT, padx=(10, 0))
    hotkey_entry = tk.Entry(top_frame, textvariable=hotkey_var, width=5)
    hotkey_entry.pack(side=tk.LEFT, padx=5)
    hotkey_entry.bind("<FocusOut>", lambda e, idx=i: on_hotkey_change(idx))
    hotkey_entry.bind("<Return>", lambda e, idx=i: on_hotkey_change(idx))

    auto_aim_var = tk.BooleanVar(value=combo.get("auto_aim", True))
    auto_aim_cb = tk.Checkbutton(
        top_frame,
        text="Aim",
        variable=auto_aim_var,
        command=lambda idx=i: on_auto_aim_change(idx),
    )
    auto_aim_cb.pack(side=tk.LEFT, padx=(10, 0))

    expand_btn = tk.Button(
        top_frame, text="▼", command=lambda idx=i: toggle_combo(idx), width=3
    )
    expand_btn.pack(side=tk.LEFT, padx=5)

    add_attack_btn = tk.Button(
        top_frame, text="+", command=lambda idx=i: add_attack(idx), width=3
    )
    add_attack_btn.pack(side=tk.LEFT, padx=2)

    batch_btn = tk.Button(
        top_frame, text="D", command=lambda idx=i: batch_input(idx), width=3
    )
    batch_btn.pack(side=tk.LEFT, padx=2)

    remove_combo_btn = tk.Button(
        top_frame, text="X", command=lambda idx=i: remove_this_combo(idx), width=3
    )
    remove_combo_btn.pack(side=tk.LEFT, padx=2)

    list_frame = tk.Frame(frame, bd=2, relief=tk.SUNKEN)
    canvas = tk.Canvas(list_frame)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.configure(yscrollcommand=scroll.set)

    container = tk.Frame(canvas)
    canvas.create_window((0, 0), window=container, anchor="nw")
    container.bind(
        "<Configure>", lambda e, c=canvas: c.configure(scrollregion=c.bbox("all"))
    )

    entries = []
    for j, attack in enumerate(combo.get("attacks", [])):
        attack_frame = tk.Frame(container)
        attack_frame.pack(fill=tk.X, pady=2)

        key_var = tk.StringVar(value=attack.get("key", ""))
        delay_var = tk.StringVar(value=str(attack.get("delay", DEFAULT_DELAY)))

        key_entry = tk.Entry(attack_frame, textvariable=key_var, width=5)
        key_entry.pack(side=tk.LEFT, padx=2)
        key_entry.bind("<KeyRelease>", lambda e, idx=i: update_combo_preview(idx))

        tk.Label(attack_frame, text=f"{j + 1}.", width=3).pack(side=tk.LEFT)
        tk.Label(attack_frame, text="ms").pack(side=tk.LEFT)
        tk.Entry(attack_frame, textvariable=delay_var, width=6).pack(
            side=tk.LEFT, padx=2
        )

        btn_minus = tk.Button(
            attack_frame,
            text="-",
            command=lambda idx=i, atk=j: remove_single_attack(idx, atk),
            width=3,
        )
        btn_minus.pack(side=tk.LEFT, padx=2)

        entries.append((key_var, delay_var))

    combo_widgets[i] = {
        "frame": frame,
        "top_frame": top_frame,
        "preview_label": preview_label,
        "hotkey_var": hotkey_var,
        "auto_aim_var": auto_aim_var,
        "expand_btn": expand_btn,
        "expanded": expanded,
        "list_frame": list_frame,
        "canvas": canvas,
        "container": container,
        "entries": entries,
    }


def on_hotkey_change(idx):
    update_attacks_from_ui()
    if idx < len(bot.combos):
        bot.combos[idx]["hotkey"] = (
            combo_widgets[idx]["hotkey_var"].get().strip().lower()
        )
    bot.save_current_profile()


def on_auto_aim_change(idx):
    update_attacks_from_ui()
    if idx < len(bot.combos):
        bot.combos[idx]["auto_aim"] = combo_widgets[idx]["auto_aim_var"].get()
    bot.save_current_profile()


def add_combo():
    update_attacks_from_ui()
    new_combo = {
        "attacks": [{"key": "", "delay": DEFAULT_DELAY}],
        "hotkey": "",
        "auto_aim": True,
    }
    bot.combos.append(new_combo)
    new_idx = len(bot.combos) - 1
    bot.combos_state[new_idx] = {
        "pressed": False,
        "idx": 0,
        "next_time": 0,
        "initial_fire": False,
    }
    bot.save_current_profile()
    bot.load_profile(bot.current_profile_name)
    refresh_ui()


def remove_combo():
    if len(bot.combos) <= 1:
        messagebox.showwarning("Aviso", "Deve ter pelo menos 1 combo!")
        return
    update_attacks_from_ui()
    bot.combos.pop()
    bot.combos_state.pop(len(bot.combos), None)
    bot.save_current_profile()
    refresh_ui()


def batch_input(combo_idx):
    dialog = tk.Toplevel(root)
    dialog.title("Input em Batch")
    dialog.geometry("350x120")
    dialog.transient(root)
    dialog.grab_set()

    tk.Label(dialog, text="Digite as teclas em sequencia (ex: qwer):").pack(pady=5)
    input_var = tk.StringVar()
    input_entry = tk.Entry(dialog, textvariable=input_var, width=30, font=("Arial", 14))
    input_entry.pack(pady=5)
    input_entry.focus()

    def apply_batch():
        text = input_var.get().strip().lower()
        if not text:
            dialog.destroy()
            return
        new_attacks = [{"key": char, "delay": DEFAULT_DELAY} for char in text]
        update_attacks_from_ui()
        if combo_idx < len(bot.combos):
            bot.combos[combo_idx]["attacks"] = new_attacks
            bot.save_current_profile()
        was_expanded = (
            combo_widgets.get(combo_idx, {}).get("expanded", tk.BooleanVar()).get()
        )
        refresh_ui()
        update_combo_preview(combo_idx)
        if was_expanded:
            cw = combo_widgets.get(combo_idx)
            if cw:
                cw["expanded"].set(True)
                cw["list_frame"].pack(fill=tk.BOTH, expand=True, pady=5)
        dialog.destroy()

    tk.Button(dialog, text="OK", command=apply_batch, width=10).pack(pady=5)
    dialog.bind("<Return>", lambda e: apply_batch())


def add_attack(combo_idx):
    update_attacks_from_ui()
    if combo_idx < len(bot.combos):
        bot.combos[combo_idx]["attacks"].append({"key": "", "delay": DEFAULT_DELAY})
        bot.save_current_profile()
    if combo_idx in combo_widgets:
        cw = combo_widgets[combo_idx]
        was_expanded = cw["expanded"].get()
        refresh_ui()
        if was_expanded:
            cw = combo_widgets.get(combo_idx)
            if cw:
                cw["expanded"].set(True)
                cw["list_frame"].pack(fill=tk.BOTH, expand=True, pady=5)
    update_combo_preview(combo_idx)


def remove_attack(combo_idx):
    update_attacks_from_ui()
    if combo_idx < len(bot.combos):
        if len(bot.combos[combo_idx]["attacks"]) > 1:
            bot.combos[combo_idx]["attacks"].pop()
    bot.save_current_profile()
    if combo_idx in combo_widgets:
        cw = combo_widgets[combo_idx]
        was_expanded = cw["expanded"].get()
        refresh_ui()
        if was_expanded:
            cw = combo_widgets.get(combo_idx)
            if cw:
                cw["expanded"].set(True)
                cw["list_frame"].pack(fill=tk.BOTH, expand=True, pady=5)


def remove_single_attack(combo_idx, attack_idx):
    update_attacks_from_ui()
    if combo_idx < len(bot.combos):
        attacks = bot.combos[combo_idx]["attacks"]
        if len(attacks) > 1 and attack_idx < len(attacks):
            attacks.pop(attack_idx)
    bot.save_current_profile()
    if combo_idx in combo_widgets:
        cw = combo_widgets[combo_idx]
        was_expanded = cw["expanded"].get()
        refresh_ui()
        if was_expanded:
            cw = combo_widgets.get(combo_idx)
            if cw:
                cw["expanded"].set(True)
                cw["list_frame"].pack(fill=tk.BOTH, expand=True, pady=5)


profile_frame = ttk.LabelFrame(content_frame, text="Profile", padding="10")
profile_frame.pack(fill=tk.X, padx=10, pady=5)

profile_combo = ttk.Combobox(
    profile_frame,
    textvariable=profile_var,
    values=bot.profiles,
    state="readonly",
    width=20,
)
profile_combo.pack(side=tk.LEFT, padx=5)
profile_combo.bind("<<ComboboxSelected>>", on_profile_select)

tk.Button(profile_frame, text="Novo", command=create_new_profile).pack(
    side=tk.LEFT, padx=2
)
tk.Button(profile_frame, text="Salvar", command=save_profile).pack(side=tk.LEFT, padx=2)
tk.Button(profile_frame, text="Excluir", command=delete_current_profile).pack(
    side=tk.LEFT, padx=2
)

combos_btn_frame = tk.Frame(content_frame)
combos_btn_frame.pack(fill=tk.X, padx=10, pady=5)
tk.Button(combos_btn_frame, text="+ Combo", command=add_combo, width=10).pack(
    side=tk.LEFT, padx=2
)
tk.Button(combos_btn_frame, text="- Combo", command=remove_combo, width=10).pack(
    side=tk.LEFT, padx=2
)

control_frame = ttk.LabelFrame(content_frame, text="Controle", padding="10")
control_frame.pack(fill=tk.X, padx=10, pady=5)

status_label = tk.Label(
    control_frame, text="Status: Parado", foreground="red", font=("Arial", 12, "bold")
)
status_label.pack(side=tk.LEFT, padx=10)


def toggle_bot():
    update_attacks_from_ui()
    if bot.running:
        bot.stop()
        status_label.config(text="Status: Parado", foreground="red")
        toggle_btn.config(text="INICIAR", bg="#4CAF50")
    else:
        bot.start()
        status_label.config(text="Status: Executando", foreground="green")
        toggle_btn.config(text="PAUSAR", bg="#f44336")


toggle_btn = tk.Button(
    control_frame,
    text="INICIAR",
    command=toggle_bot,
    bg="#4CAF50",
    fg="white",
    font=("Arial", 10, "bold"),
    width=10,
)
toggle_btn.pack(side=tk.LEFT, padx=10)

aim_info_label = tk.Label(
    content_frame, text="Aguardando deteccao...", foreground="gray", font=("Arial", 9)
)
aim_info_label.pack(pady=5)


def run_loop():
    if bot.running:
        current = time.time()

        auto_aim_pressed = False
        any_pressed = False

        for i, combo in enumerate(bot.combos):
            if i >= len(bot.combos_state):
                continue

            state = bot.combos_state[i]
            attacks = combo.get("attacks", [])

            if state["pressed"]:
                any_pressed = True
                if combo.get("auto_aim", True):
                    auto_aim_pressed = True

        if auto_aim_pressed:
            detections = bot.target_detector.detect()
            if detections:
                region_offset = (
                    bot.target_detector.region["left"],
                    bot.target_detector.region["top"],
                )
                bot.target_detector.update_clamped_pos(region_offset)
                clamped_pos = bot.target_detector.get_closest_target_pos()
                raw_pos = bot.target_detector.get_raw_target_pos()
                if clamped_pos:
                    cx, cy = clamped_pos
                    rx, ry = raw_pos if raw_pos else (0, 0)
                    aim_info_label.config(
                        text=f"AIM: ({cx}, {cy}) | Target: ({rx}, {ry}) | Qtd: {len(detections)}",
                        foreground="green",
                    )
                    try:
                        pyautogui.moveTo(cx, cy, duration=0)
                    except:
                        pass
            else:
                aim_info_label.config(
                    text="Nenhum alvo encontrado", foreground="orange"
                )
        elif not any_pressed:
            aim_info_label.config(text="Aguardando combo...", foreground="gray")

        for i, combo in enumerate(bot.combos):
            if i >= len(bot.combos_state):
                continue

            state = bot.combos_state[i]
            attacks = combo.get("attacks", [])

            if (
                state["pressed"]
                and attacks
                and (current >= state["next_time"] or state["initial_fire"])
            ):
                attack = attacks[state["idx"]]
                key = attack.get("key", "")
                delay_ms = attack.get("delay", DEFAULT_DELAY)

                if key:
                    press_key(key)

                state["idx"] = (state["idx"] + 1) % len(attacks)
                state["next_time"] = current + (delay_ms / 1000.0)
                state["initial_fire"] = False

    root.after(15, run_loop)


refresh_ui()
root.after(15, poll_keyboard)
root.after(100, run_loop)
root.mainloop()
