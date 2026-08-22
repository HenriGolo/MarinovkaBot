import copy
import json
import os
from threading import RLock
from typing import Any

from utilitaires.config import config


class JsonStore:
    def __init__(self, filename: str):
        self.filename = filename
        self._lock = RLock()
        self._data: dict[str, Any] = {}
        self._last_mtime: float = 0.0
        self._load()

    # --------- internals ---------

    def _load(self):
        try:
            mtime = os.path.getmtime(self.filename)
            if mtime == self._last_mtime:
                return

            with open(self.filename, "r") as f:
                self._data = json.load(f)

            self._last_mtime = mtime

        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}
            self._last_mtime = 0.0

    def _write(self):
        with open(self.filename, "w") as f:
            json.dump(self._data, f, **config.json_format)
        self._last_mtime = os.path.getmtime(self.filename)

    # --------- public API ---------

    def data(self) -> dict:
        with self._lock:
            self._load()
            return self._data

    def save(self):
        with self._lock:
            self._write()

    def update(self, func):
        """Mutation directe + reload safe"""
        with self._lock:
            self._load()
            result = func(self._data)
            self._write()
            return result


class Transaction:
    def __init__(self, store: JsonStore):
        self.store = store
        self._backup = None

    def __enter__(self):
        self.store._lock.acquire()
        self.store._load()
        self._backup = copy.deepcopy(self.store._data)
        return self.store._data

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            # rollback
            self.store._data = self._backup
        else:
            # commit
            self.store._write()

        self.store._lock.release()
        return False  # ne supprime pas les exceptions
