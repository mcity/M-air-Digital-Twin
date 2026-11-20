"""Minimal stand-in for the `keyboard` package on Linux/X11.

The real `keyboard` package refuses to run without root on Linux. Project AirSim's
keyboard_control.py only calls keyboard.is_pressed(name), so this provides that
on top of pynput, which reads keys from the X session without root.
Keys are read globally: they register whichever window has focus.
"""
import os
import sys
import threading
from pynput import keyboard as _kb

_pressed = set()
_lock = threading.Lock()
_DEBUG = bool(os.environ.get("KEYBOARD_SHIM_DEBUG"))


def _name(key):
    if isinstance(key, _kb.KeyCode):
        return key.char.lower() if key.char else None
    return key.name  # 'up', 'down', 'left', 'right', 'space', ...


def _on_press(key):
    n = _name(key)
    if _DEBUG:
        print("[keyboard shim] press %r -> %r" % (key, n), file=sys.stderr, flush=True)
    if n:
        with _lock:
            _pressed.add(n)


def _on_release(key):
    n = _name(key)
    if n:
        with _lock:
            _pressed.discard(n)


_listener = _kb.Listener(on_press=_on_press, on_release=_on_release)
_listener.daemon = True
_listener.start()


def is_pressed(name):
    with _lock:
        return str(name).lower() in _pressed
