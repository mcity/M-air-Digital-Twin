"""uikit.py - what every window here needs to fit on the screen it is opened on.

The windows were laid out on a tall monitor. On a 1080 line screen, less the taskbar and the
window's own title bar, the flight planner's right hand column ran off the bottom and took the
Fly button with it. Two things fix that: a window never asks for more than the screen has, and a
column of panels scrolls when it is taller than the room it is given.
"""
import tkinter as tk
from tkinter import ttk

# The taskbar, the title bar and the window border are not part of the size a window asks for.
SCREEN_MARGIN_W = 40
SCREEN_MARGIN_H = 110


def fit_to_screen(window, width, height, min_width, min_height):
    """Ask for width x height, but never more than the screen has room for."""
    screen_w, screen_h = window.winfo_screenwidth(), window.winfo_screenheight()
    w = min(width, screen_w - SCREEN_MARGIN_W)
    h = min(height, screen_h - SCREEN_MARGIN_H)
    window.geometry("%dx%d+%d+%d" % (w, h, max(0, (screen_w - w) // 2), 10))
    window.minsize(min(min_width, w), min(min_height, h))


class ScrollColumn(ttk.Frame):
    """A column that scrolls vertically when what it holds is taller than the room it is given.

    Put widgets in .inner. With stretch, .inner is as wide as the column, for panels laid across
    the whole window; without, the column is as wide as what it holds. With room to spare, .inner
    is stretched to the full height, so a widget in it packed with expand=True still grows.

    The wheel scrolls the column wherever the pointer is over it, except over widgets that scroll
    themselves: lists, logs and maps keep the wheel. Comboboxes in a column lose theirs, because
    otherwise scrolling past one quietly changes its value."""

    WATCH_MS = 250

    def __init__(self, parent, stretch=False, **kw):
        super().__init__(parent, **kw)
        self.stretch = stretch
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, yscrollincrement=20)
        background = ttk.Style().lookup("TFrame", "background")
        if background:
            self.canvas.configure(background=background)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.canvas)
        self._item = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self._last = None
        self.inner.bind("<Configure>", self._fit)
        self.canvas.bind("<Configure>", self._fit)
        self.bind_all("<MouseWheel>", self._wheel, add="+")
        self.bind_class("TCombobox", "<MouseWheel>", lambda _e: None)
        # A panel that grows (a readout wrapping onto more lines) changes what .inner asks for
        # without changing its size, and Tk sends no event for that. So it is watched.
        self.after(self.WATCH_MS, self._watch)

    def _fit(self, _event=None):
        want_w, want_h = self.inner.winfo_reqwidth(), self.inner.winfo_reqheight()
        have_w, have_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        # Ask for the whole of what it holds, so pack gives the column its room before anything
        # packed after it; what the window cannot give, it scrolls.
        if (int(self.canvas.cget("width")), int(self.canvas.cget("height"))) != (want_w, want_h):
            self.canvas.configure(width=want_w, height=want_h)
        width = have_w if (self.stretch and have_w > 1) else want_w
        height = max(want_h, have_h)
        self.canvas.itemconfigure(self._item, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))
        self._last = (want_w, want_h, have_w, have_h)

    def _watch(self):
        try:
            now = (self.inner.winfo_reqwidth(), self.inner.winfo_reqheight(),
                   self.canvas.winfo_width(), self.canvas.winfo_height())
        except tk.TclError:
            return   # the window has closed
        if now != self._last:
            self._fit()
        self.after(self.WATCH_MS, self._watch)

    def _wheel(self, event):
        path, inner = str(event.widget), str(self.inner)
        if not (path == inner or path.startswith(inner + ".")) or ".popdown" in path:
            return
        if isinstance(event.widget, (tk.Text, tk.Listbox, tk.Canvas, ttk.Treeview)):
            return
        if self.inner.winfo_reqheight() <= self.canvas.winfo_height():
            return
        # Windows reports 120 a notch: three steps of 20 pixels. A touchpad reports less.
        steps = -int(event.delta / 40) or (-1 if event.delta > 0 else 1)
        self.canvas.yview_scroll(steps, "units")
