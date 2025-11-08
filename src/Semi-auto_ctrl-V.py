#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Semi-auto_ctrl-V — Mantiene ventana minimizada tras inyección
- No se restaura automáticamente al finalizar
- Basado en v1.6.1 (tooltips + interfaz limpia)
"""

import threading, time, queue, os, tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import pyautogui, pyperclip
from pynput import mouse
from pynput.mouse import Button

# ---------- CONFIG ----------
DEFAULT_SPEED_MS = 10
MAX_CHARS = 20000
CLICK_WAIT_AFTER = 0.18
HISTORY_FILE = ".Semi-auto_ctrl-V_HISTORIAL.txt"
HISTORY_MAX = 20
pyautogui.FAILSAFE = True
# ----------------------------

# ===== Clase Tooltip =====
class Tooltip:
    def __init__(self, widget, text, delay=600):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tipwindow = None
        self.id = None
        self.widget.bind("<Enter>", self._schedule)
        self.widget.bind("<Leave>", self._hide)

    def _schedule(self, event=None):
        self._cancel()
        self.id = self.widget.after(self.delay, self._show)

    def _show(self):
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert") or (0, 0, 0, 0)
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            wraplength=260,
            font=("Segoe UI", 9)
        )
        label.pack(ipadx=6, ipady=4)

    def _hide(self, event=None):
        self._cancel()
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

    def _cancel(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
# ==================================================

class SmartInjector:
    def __init__(self, root):
        self.root = root
        self.root.title("Semi-auto_ctrl-V — Turbo & Paste")
        self.root.geometry("1080x720")
        self.root.minsize(900, 600)

        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure("Primary.TButton", padding=8, foreground="white", background="#2563eb", font=("Segoe UI", 10, "bold"))
        style.map("Primary.TButton", background=[("active", "#1e40af")])
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TCheckbutton", font=("Segoe UI", 9))

        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)

        ttk.Label(main, text="Texto a inyectar", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.text_area = scrolledtext.ScrolledText(main, wrap="word", width=100, height=20,
                                                  font=("Consolas", 11), bg="#f8fafc", relief="solid", bd=1)
        self.text_area.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 10))

        side = ttk.Frame(main, padding=(10, 0))
        side.grid(row=1, column=2, sticky="ns")
        side.columnconfigure(0, weight=1)

        # Prefijo / Sufijo
        ttk.Label(side, text="Prefijo").grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.prefix_var = tk.StringVar()
        prefix_entry = ttk.Entry(side, textvariable=self.prefix_var, width=30)
        prefix_entry.grid(row=1, column=0, sticky="we", pady=(0, 6))
        Tooltip(prefix_entry, "Texto que se añadirá automáticamente al principio del mensaje.\nEjemplo: 'Comando: ' o '/say '")

        ttk.Label(side, text="Sufijo").grid(row=2, column=0, sticky="w", pady=(4, 2))
        self.suffix_var = tk.StringVar()
        suffix_entry = ttk.Entry(side, textvariable=self.suffix_var, width=30)
        suffix_entry.grid(row=3, column=0, sticky="we", pady=(0, 10))
        Tooltip(suffix_entry, "Texto que se añadirá automáticamente al final del mensaje.\nEjemplo: '.' o '\\n' para un salto de línea.")

        ttk.Label(side, text="Modo de entrada").grid(row=4, column=0, sticky="w", pady=(0, 2))
        self.mode_var = tk.StringVar(value="Paste")
        ttk.Combobox(side, textvariable=self.mode_var, values=["Paste", "Type", "Hybrid"], width=15, state="readonly").grid(row=5, column=0, sticky="we", pady=(0, 8))

        vel_frame = ttk.Frame(side)
        vel_frame.grid(row=6, column=0, sticky="we", pady=(0, 6))
        ttk.Label(vel_frame, text="Velocidad (ms/car):").pack(side="left")
        self.speed_var = tk.StringVar(value=str(DEFAULT_SPEED_MS))
        ttk.Spinbox(vel_frame, from_=0, to=500, increment=1, textvariable=self.speed_var, width=6).pack(side="left", padx=(6, 0))

        self.turbo_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(side, text="Turbo (máxima velocidad)", variable=self.turbo_var).grid(row=7, column=0, sticky="w", pady=(4, 8))

        self.btn_prepare = ttk.Button(side, text="⚡ Preparar inyección (click derecho)", style="Primary.TButton", command=self.prepare)
        self.btn_prepare.grid(row=8, column=0, sticky="we", pady=(8, 4))
        self.btn_cancel = ttk.Button(side, text="✖ Cancelar", command=self.cancel, state="disabled")
        self.btn_cancel.grid(row=9, column=0, sticky="we", pady=(0, 6))

        ttk.Separator(side).grid(row=10, column=0, sticky="we", pady=(8, 8))
        ttk.Button(side, text="📋 Cargar portapapeles", command=self.load_clip).grid(row=11, column=0, sticky="we", pady=(0, 4))
        ttk.Button(side, text="🧹 Limpiar texto", command=self.clear_text).grid(row=12, column=0, sticky="we", pady=(0, 4))
        ttk.Button(side, text="❓ Ayuda", command=self.show_help).grid(row=13, column=0, sticky="we", pady=(4, 0))

        hist_frame = ttk.LabelFrame(main, text="Historial (últimos textos)", padding=6)
        hist_frame.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(10, 0))
        hist_frame.columnconfigure(0, weight=1)
        self.history_list = tk.Listbox(hist_frame, height=5, font=("Consolas", 9))
        self.history_list.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        hist_buttons = ttk.Frame(hist_frame)
        hist_buttons.grid(row=1, column=0, sticky="we")
        ttk.Button(hist_buttons, text="⤓ Cargar seleccionado", command=self.load_selected_history).pack(side="left")
        ttk.Button(hist_buttons, text="✖ Borrar seleccionado", command=self.delete_selected_history).pack(side="left", padx=(8, 0))
        ttk.Button(hist_buttons, text="🗑️ Limpiar historial", command=self.clear_history).pack(side="left", padx=(8, 0))

        bottom = ttk.Frame(main)
        bottom.grid(row=3, column=0, columnspan=3, sticky="we", pady=(10, 0))
        self.progress = ttk.Progressbar(bottom, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(0, 4))
        self.status_var = tk.StringVar(value="Listo — pega texto y pulsa Preparar inyección.")
        self.status_label = ttk.Label(bottom, textvariable=self.status_var, relief="sunken", anchor="w", padding=6)
        self.status_label.pack(fill="x")

        self.text_area.bind("<<Modified>>", self._on_text_mod)
        self.root.bind("<Escape>", lambda e: self.cancel())
        self._payload = None
        self._q = queue.Queue()
        self.mouse_listener = None
        self._waiting = False
        self._load_history_file()
        self.load_clip()

    # ---------- UX ----------
    def _set_status(self, msg, color=None):
        self.status_var.set(msg)
        if color:
            self.status_label.configure(foreground=color)

    def _on_text_mod(self, _e=None):
        self._update_char_count()
        try:
            self.text_area.edit_modified(False)
        except:
            pass

    def _update_char_count(self):
        n = len(self.text_area.get("1.0", tk.END).rstrip("\n"))
        self._set_status(f"{n} caracteres (límite {MAX_CHARS}).", "#2563eb")

    def clear_text(self):
        self.text_area.delete("1.0", tk.END)
        self._update_char_count()
        self._set_status("Texto borrado.", "#2563eb")

    def load_clip(self):
        try:
            txt = pyperclip.paste()
        except:
            txt = ""
        if txt:
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert(tk.END, txt)
            self._set_status("Texto cargado desde portapapeles.", "#2563eb")
        else:
            self._set_status("Portapapeles vacío.", "#2563eb")
        self._update_char_count()

    # ---------- Historial ----------
    def _load_history_file(self):
        self.history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                self.history = list(reversed([ln.strip() for ln in f.readlines() if ln.strip()]))
        self._refresh_history_list()

    def _save_history_file(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                for ln in reversed(self.history):
                    f.write(ln + "\n")
        except:
            pass

    def _refresh_history_list(self):
        self.history_list.delete(0, tk.END)
        for i, txt in enumerate(self.history):
            summary = txt.replace("\n", " ↵ ")
            if len(summary) > 90:
                summary = summary[:87] + "..."
            self.history_list.insert(tk.END, f"{i+1}. {summary}")

    def _add_to_history(self, text):
        if not text.strip():
            return
        if text in self.history:
            self.history.remove(text)
        self.history.insert(0, text)
        self.history = self.history[:HISTORY_MAX]
        self._refresh_history_list()
        self._save_history_file()

    def load_selected_history(self):
        sel = self.history_list.curselection()
        if not sel:
            return
        idx = sel[0]
        txt = self.history[idx]
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert(tk.END, txt)
        self._set_status("Texto cargado desde historial.", "#2563eb")

    def delete_selected_history(self):
        sel = self.history_list.curselection()
        if not sel:
            return
        idx = sel[0]
        del self.history[idx]
        self._refresh_history_list()
        self._save_history_file()

    def clear_history(self):
        if messagebox.askyesno("Confirmar", "¿Borrar todo el historial?"):
            self.history = []
            self._refresh_history_list()
            self._save_history_file()
            self._set_status("Historial limpiado.", "#2563eb")

    # ---------- Inyección ----------
    def prepare(self):
        if self._waiting:
            return
        text = self.text_area.get("1.0", tk.END).rstrip("\n")
        if not text:
            messagebox.showwarning("Sin texto", "Escribe o pega algo primero.")
            return
        full_text = (self.prefix_var.get() or "") + text + (self.suffix_var.get() or "")
        self._add_to_history(full_text)
        try:
            speed_ms = max(0.0, float(self.speed_var.get()))
        except:
            speed_ms = DEFAULT_SPEED_MS
        self._payload = {
            "text": full_text,
            "mode": self.mode_var.get(),
            "turbo": self.turbo_var.get(),
            "speed_ms": speed_ms,
        }
        self._set_status("Esperando click derecho...", "#2563eb")
        self._waiting = True
        self.btn_cancel.config(state="normal")
        self.btn_prepare.config(state="disabled")
        self.root.iconify()
        threading.Thread(target=self._mouse_listener, daemon=True).start()
        threading.Thread(target=self._wait_click, daemon=True).start()

    def _mouse_listener(self):
        def on_click(x, y, button, pressed):
            if button == Button.right and pressed:
                self._q.put(("right_click", (x, y)))
                return False
        try:
            with mouse.Listener(on_click=on_click, suppress=False) as listener:
                self.mouse_listener = listener
                listener.join()
        except:
            self._q.put(("error", None))

    def _wait_click(self):
        try:
            event, _ = self._q.get(timeout=60)
        except:
            return self._done("Tiempo agotado.", "red")
        if event == "right_click":
            time.sleep(CLICK_WAIT_AFTER)
            threading.Thread(target=self._inject, daemon=True).start()

    def _inject(self):
        p = self._payload
        txt = p["text"]
        mode = p["mode"]
        turbo = p["turbo"]
        interval = 0 if turbo else p["speed_ms"] / 1000.0
        try:
            pyautogui.press("esc")
            x, y = pyautogui.position()
            pyautogui.moveRel(1, 1, duration=0.01)
            pyautogui.moveTo(x, y, duration=0.01)
            if mode == "Paste":
                pyperclip.copy(txt)
                time.sleep(0.02)
                pyautogui.hotkey("ctrl", "v")
            elif mode == "Hybrid":
                pyperclip.copy(txt)
                pyautogui.hotkey("ctrl", "v")
                pyautogui.typewrite(txt[-3:], interval=interval)
            else:
                for i, ch in enumerate(txt, 1):
                    pyautogui.typewrite(ch, interval=interval)
                    self.progress.configure(value=int((i / len(txt)) * 100))
            self.progress.configure(value=100)
            self._done("✔ Inyección completada.", "green")
        except pyautogui.FailSafeException:
            self._done("Abortada (failsafe).", "red")
        except Exception as e:
            self._done(f"Error: {e}", "red")

    def cancel(self):
        self._waiting = False
        self.btn_cancel.config(state="disabled")
        self.btn_prepare.config(state="normal")
        self._set_status("Cancelado.", "red")

    def _done(self, msg, color):
        """No restaura ventana al finalizar (permanece minimizada)."""
        self._waiting = False
        def end():
            self.btn_cancel.config(state="disabled")
            self.btn_prepare.config(state="normal")
            self.progress["value"] = 0
            self._set_status(msg, color)
            # 👇 No se deiconifica
        self.root.after(0, end)

    def show_help(self):
        messagebox.showinfo(
            "Ayuda — Semi-auto_ctrl-V",
            "1️⃣ Escribe o pega el texto.\n"
            "2️⃣ Pulsa 'Preparar inyección'.\n"
            "3️⃣ Haz click derecho donde quieras escribir.\n"
            "4️⃣ El texto se inyectará según el modo (Paste/Type/Hybrid).\n\n"
            "💡 Usa Turbo para máxima velocidad.\n"
            "⎋ Esc cancela, FailSafe moviendo ratón a esquina sup. izq."
        )


def main():
    root = tk.Tk()
    SmartInjector(root)
    root.mainloop()


if __name__ == "__main__":
    main()
