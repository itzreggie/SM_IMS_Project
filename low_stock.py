from tkinter import *
from tkinter import ttk, messagebox
import sqlite3
import os
from contextlib import closing

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOW_STOCK_THRESHOLD = 5
SETTINGS_TABLE = "settings"
LOW_STOCK_THRESHOLD_KEY = "low_stock_threshold"
_CACHED_THRESHOLD = None


def _db_path():
    return os.path.join(BASE_DIR, "ims.db")


def _ensure_settings_table():
    with closing(sqlite3.connect(_db_path())) as con:
        cur = con.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)"
        )
        con.commit()


def get_low_stock_threshold():
    global _CACHED_THRESHOLD
    if _CACHED_THRESHOLD is not None:
        return _CACHED_THRESHOLD

    _ensure_settings_table()
    with closing(sqlite3.connect(_db_path())) as con:
        cur = con.cursor()
        cur.execute(
            "SELECT value FROM settings WHERE key = ?",
            (LOW_STOCK_THRESHOLD_KEY,),
        )
        row = cur.fetchone()

    try:
        value = int(row[0]) if row else DEFAULT_LOW_STOCK_THRESHOLD
    except (TypeError, ValueError):
        value = DEFAULT_LOW_STOCK_THRESHOLD
    if value < 0:
        value = DEFAULT_LOW_STOCK_THRESHOLD

    _CACHED_THRESHOLD = value
    return value


def set_low_stock_threshold(value):
    global _CACHED_THRESHOLD
    try:
        clean_value = int(value)
    except (TypeError, ValueError):
        clean_value = DEFAULT_LOW_STOCK_THRESHOLD
    clean_value = max(0, clean_value)
    _ensure_settings_table()
    with closing(sqlite3.connect(_db_path())) as con:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO settings(key,value) VALUES(?,?)\n"
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (LOW_STOCK_THRESHOLD_KEY, str(clean_value)),
        )
        con.commit()
    _CACHED_THRESHOLD = clean_value


def reset_cached_threshold():
    global _CACHED_THRESHOLD
    _CACHED_THRESHOLD = None


class lowStockClass:
    def __init__(self, root, threshold=None):
        self.root = root
        self.root.geometry("850x500+350+200")
        self.root.resizable(False, False)
        self.root.config(bg="white")
        self.root.focus_force()

        resolved_threshold = (
            threshold if threshold is not None else get_low_stock_threshold()
        )
        self.var_threshold = StringVar(value=str(resolved_threshold))

        title = Label(
            self.root,
            text="Low Stock Monitor",
            font=("goudy old style", 30, "bold"),
            bg="#184a45",
            fg="white",
            bd=3,
            relief=RIDGE,
        )
        title.pack(side=TOP, fill=X, padx=10, pady=20)

        control_frame = Frame(self.root, bg="white")
        control_frame.pack(fill=X, padx=20)

        lbl_threshold = Label(
            control_frame,
            text="Alert when quantity is at or below:",
            font=("goudy old style", 16),
            bg="white",
        )
        lbl_threshold.pack(side=LEFT)

        Entry(
            control_frame,
            textvariable=self.var_threshold,
            font=("goudy old style", 16),
            width=5,
            justify=CENTER,
            bd=2,
            relief=RIDGE,
        ).pack(side=LEFT, padx=10)

        Button(
            control_frame,
            text="Refresh",
            font=("goudy old style", 14, "bold"),
            bg="#4caf50",
            fg="white",
            cursor="hand2",
            command=self.refresh_data,
        ).pack(side=LEFT)

        Button(
            control_frame,
            text="Save Threshold",
            font=("goudy old style", 14, "bold"),
            bg="#560591",
            fg="white",
            cursor="hand2",
            command=self.save_threshold,
        ).pack(side=LEFT, padx=10)

        self.lbl_summary = Label(
            self.root,
            text="",
            font=("times new roman", 16),
            bg="white",
            fg="#333333",
        )
        self.lbl_summary.pack(fill=X, padx=20, pady=(10, 0))

        tree_frame = Frame(self.root, bd=3, relief=RIDGE)
        tree_frame.pack(fill=BOTH, expand=1, padx=20, pady=20)

        scrolly = Scrollbar(tree_frame, orient=VERTICAL)
        scrollx = Scrollbar(tree_frame, orient=HORIZONTAL)
        self.LowStockTable = ttk.Treeview(
            tree_frame,
            columns=("pid", "name", "qty", "status"),
            yscrollcommand=scrolly.set,
            xscrollcommand=scrollx.set,
        )
        scrollx.pack(side=BOTTOM, fill=X)
        scrolly.pack(side=RIGHT, fill=Y)
        scrollx.config(command=self.LowStockTable.xview)
        scrolly.config(command=self.LowStockTable.yview)

        self.LowStockTable.heading("pid", text="Product ID")
        self.LowStockTable.heading("name", text="Name")
        self.LowStockTable.heading("qty", text="Quantity")
        self.LowStockTable.heading("status", text="Status")
        self.LowStockTable["show"] = "headings"
        self.LowStockTable.column("pid", width=120)
        self.LowStockTable.column("name", width=220)
        self.LowStockTable.column("qty", width=120)
        self.LowStockTable.column("status", width=120)
        self.LowStockTable.pack(fill=BOTH, expand=1)

        self.refresh_data()

    def refresh_data(self):
        threshold = self._current_threshold()
        try:
            rows = self._fetch_low_stock_rows()
            filtered = [row for row in rows if self._qty_value(row[2]) <= threshold]
            filtered.sort(key=lambda row: self._qty_value(row[2]))
            self._populate_table(filtered)
            self.lbl_summary.config(
                text=f"Products with quantity <= {threshold}: {len(filtered)}"
            )
        except Exception as ex:
            messagebox.showerror("Error", f"Unable to load low stock data: {ex}", parent=self.root)

    def save_threshold(self):
        threshold = self._current_threshold()
        try:
            set_low_stock_threshold(threshold)
            messagebox.showinfo(
                "Threshold Saved",
                f"Alert threshold updated to {threshold} units.",
                parent=self.root,
            )
            self.refresh_data()
        except Exception as ex:
            messagebox.showerror(
                "Error", f"Unable to save threshold: {ex}", parent=self.root
            )

    def _current_threshold(self):
        raw_value = self.var_threshold.get().strip()
        try:
            threshold = int(raw_value)
            if threshold < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Value", "Threshold must be a non-negative integer.", parent=self.root)
            threshold = DEFAULT_LOW_STOCK_THRESHOLD
            self.var_threshold.set(str(threshold))
        return threshold

    def _fetch_low_stock_rows(self):
        with closing(sqlite3.connect(_db_path())) as con:
            cur = con.cursor()
            cur.execute("select pid, name, qty, status from product")
            return cur.fetchall()

    def _populate_table(self, rows):
        self.LowStockTable.delete(*self.LowStockTable.get_children())
        for pid, name, qty, status in rows:
            self.LowStockTable.insert("", END, values=(pid, name, qty, status))

    def _qty_value(self, qty):
        try:
            return int(str(qty).strip())
        except (ValueError, TypeError):
            return float("inf")


if __name__ == "__main__":
    root = Tk()
    obj = lowStockClass(root)
    root.mainloop()
