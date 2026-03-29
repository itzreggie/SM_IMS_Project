"""Unit tests for helper utilities introduced during Task T3."""
import os
import shutil
import sqlite3
import unittest
from pathlib import Path
from tkinter import Tk
from contextlib import closing

import create_db
import low_stock
from billing import billClass
from product import productClass

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "ims.db"
BACKUP_PATH = BASE_DIR / "ims.db.copilot_backup"
BACKUP_EXISTS = False
TABLES_TO_CLEAR = ("employee", "supplier", "category", "product", "settings")


def setUpModule():
    global BACKUP_EXISTS
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, BACKUP_PATH)
        BACKUP_EXISTS = True
    else:
        BACKUP_EXISTS = False
    reset_database()


def tearDownModule():
    if BACKUP_EXISTS:
        if BACKUP_PATH.exists():
            shutil.copy2(BACKUP_PATH, DB_PATH)
            BACKUP_PATH.unlink()
    else:
        if DB_PATH.exists():
            DB_PATH.unlink()
        if BACKUP_PATH.exists():
            BACKUP_PATH.unlink()


def reset_database():
    create_db.create_db()
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.cursor()
        for table in TABLES_TO_CLEAR:
            cur.execute(f"DELETE FROM {table}")
        con.commit()


class LowStockSettingsTest(unittest.TestCase):
    def setUp(self):
        reset_database()
        low_stock.reset_cached_threshold()

    def test_get_threshold_returns_default_when_missing(self):
        value = low_stock.get_low_stock_threshold()
        self.assertEqual(value, low_stock.DEFAULT_LOW_STOCK_THRESHOLD)

    def test_set_threshold_persists_value(self):
        low_stock.set_low_stock_threshold(12)
        low_stock.reset_cached_threshold()
        self.assertEqual(low_stock.get_low_stock_threshold(), 12)

    def test_set_threshold_clamps_negative_values(self):
        low_stock.set_low_stock_threshold(-4)
        low_stock.reset_cached_threshold()
        self.assertEqual(low_stock.get_low_stock_threshold(), 0)


class ProductHelperTest(unittest.TestCase):
    def setUp(self):
        self.product_helper = productClass.__new__(productClass)

    def test_safe_qty_returns_integer(self):
        self.assertEqual(self.product_helper._safe_qty_value("7"), 7)

    def test_safe_qty_clamps_negative_to_zero(self):
        self.assertEqual(self.product_helper._safe_qty_value("-3"), 0)

    def test_safe_qty_handles_invalid_values(self):
        self.assertIsNone(self.product_helper._safe_qty_value("not-a-number"))


class BillingHelpersTest(unittest.TestCase):
    def setUp(self):
        reset_database()
        sample_rows = [
            ("Phones", "ACME", "Phone Alpha", "10", "11", "Active"),
            ("Phones", "ACME", "Phone Beta", "9", "0", "Inactive"),
            ("Audio", "ACME", "Speaker Mini", "15", "5", "Active"),
        ]
        with closing(sqlite3.connect(DB_PATH)) as con:
            cur = con.cursor()
            cur.executemany(
                "insert into product(Category,Supplier,name,price,qty,status) values (?,?,?,?,?,?)",
                sample_rows,
            )
            con.commit()
        self.root = Tk()
        self.root.withdraw()
        self.billing = billClass(self.root)

    def tearDown(self):
        self.root.destroy()

    def test_fetch_and_populate_only_displays_active_products(self):
        rows = self.billing._fetch_products(
            "select pid,name,price,qty,status from product where status='Active' order by pid"
        )
        self.billing._populate_product_table([])
        self.billing._populate_product_table(rows)
        displayed = [
            tuple(self.billing.product_Table.item(item)["values"])
            for item in self.billing.product_Table.get_children()
        ]
        normalize = lambda seq: [tuple(str(value) for value in entry) for entry in seq]
        self.assertEqual(normalize(displayed), normalize(rows))
        for entry in displayed:
            self.assertEqual(entry[4], "Active")


if __name__ == "__main__":
    unittest.main()
