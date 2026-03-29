"""Integration tests for Task T4 scenarios."""
import os
import shutil
import sqlite3
import unittest
from contextlib import closing, ExitStack
from pathlib import Path
from tkinter import END, Tk, TclError
from unittest import mock

import billing
import create_db
import dashboard
import low_stock
import product
import sales

BASE_DIR = Path(__file__).resolve().parent.parent
if Path.cwd() != BASE_DIR:
    os.chdir(BASE_DIR)
DB_PATH = BASE_DIR / "ims.db"
BACKUP_PATH = BASE_DIR / "ims.db.integration_backup"
BILL_DIR = BASE_DIR / "bill"
TABLES_TO_CLEAR = ("employee", "supplier", "category", "product", "settings")
BACKUP_EXISTS = False


def setUpModule():
    global BACKUP_EXISTS
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, BACKUP_PATH)
        BACKUP_EXISTS = True
    else:
        BACKUP_EXISTS = False
    reset_database()


def tearDownModule():
    if BACKUP_EXISTS and BACKUP_PATH.exists():
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


class IntegrationTestCase(unittest.TestCase):
    def setUp(self):
        reset_database()
        low_stock.reset_cached_threshold()
        BILL_DIR.mkdir(exist_ok=True)
        self._exit_stack = ExitStack()
        self.addCleanup(self._exit_stack.close)
        self._patch_messageboxes()

    def _patch_messageboxes(self):
        prompt_defaults = {"askyesno": True, "askquestion": True, "askokcancel": True}
        for module in (low_stock, billing, sales, dashboard, product):
            mb = getattr(module, "messagebox", None)
            if mb is None:
                continue
            for name in ("showinfo", "showerror", "showwarning", "askyesno", "askquestion", "askokcancel"):
                if hasattr(mb, name):
                    return_value = prompt_defaults.get(name)
                    self._exit_stack.enter_context(
                        mock.patch.object(module.messagebox, name, return_value=return_value)
                    )

    def make_root(self):
        root = Tk()
        root.withdraw()
        self.addCleanup(lambda r=root: self._safe_destroy(r))
        return root

    def _safe_destroy(self, root):
        try:
            if root.winfo_exists():
                root.destroy()
        except TclError:
            pass


class LowStockIntegrationTest(IntegrationTestCase):
    def test_threshold_propagation_shows_filtered_rows(self):
        custom_threshold = 4
        low_stock.set_low_stock_threshold(custom_threshold)
        low_stock.reset_cached_threshold()
        sample_products = [
            ("Phones", "ACME", "Phone Mini", "199", "2", "Active"),
            ("Phones", "ACME", "Phone Plus", "249", "4", "Active"),
            ("Audio", "ACME", "Speaker Pro", "149", "7", "Active"),
            ("Audio", "ACME", "Earbuds", "79", "0", "Inactive"),
        ]
        with closing(sqlite3.connect(DB_PATH)) as con:
            cur = con.cursor()
            cur.executemany(
                "insert into product(Category,Supplier,name,price,qty,status) values (?,?,?,?,?,?)",
                sample_products,
            )
            con.commit()
            cur.execute("select pid,name,qty,status from product")
            db_rows = cur.fetchall()

        root = self.make_root()
        window = low_stock.lowStockClass(root)
        root.update_idletasks()

        displayed_rows = [
            tuple(str(value) for value in window.LowStockTable.item(item)["values"])
            for item in window.LowStockTable.get_children()
        ]
        expected_rows = [
            (str(pid), str(name), str(qty), str(status))
            for pid, name, qty, status in db_rows
            if int(str(qty)) <= custom_threshold
        ]
        expected_rows.sort(key=lambda row: int(row[2]))

        self.assertEqual(displayed_rows, expected_rows)
        expected_summary = f"Products with quantity <= {custom_threshold}: {len(expected_rows)}"
        self.assertEqual(window.lbl_summary.cget("text"), expected_summary)
        self.assertEqual(low_stock.get_low_stock_threshold(), custom_threshold)


class BillingSalesIntegrationTest(IntegrationTestCase):
    def test_billing_flow_updates_stock_and_sales_listing(self):
        product_row = ("Phones", "ACME", "Store Speaker", "50", "5", "Active")
        with closing(sqlite3.connect(DB_PATH)) as con:
            cur = con.cursor()
            cur.execute(
                "insert into product(Category,Supplier,name,price,qty,status) values (?,?,?,?,?,?)",
                product_row,
            )
            pid = cur.lastrowid
            con.commit()

        billing_root = self.make_root()
        billing_window = billing.billClass(billing_root)
        billing_root.update_idletasks()
        billing_window.var_cname.set("Integration Customer")
        billing_window.var_contact.set("9999999999")
        billing_window.var_pid.set(str(pid))
        billing_window.var_pname.set(product_row[2])
        billing_window.var_price.set(product_row[3])
        billing_window.var_qty.set("2")
        billing_window.var_stock.set(product_row[4])
        billing_window.add_update_cart()
        billing_window.generate_bill()
        invoice_id = str(billing_window.invoice)
        invoice_file = BILL_DIR / f"{invoice_id}.txt"
        self.addCleanup(lambda path=invoice_file: path.exists() and path.unlink())
        self.assertTrue(invoice_file.exists())

        with closing(sqlite3.connect(DB_PATH)) as con:
            cur = con.cursor()
            qty, status = cur.execute("select qty,status from product where pid=?", (pid,)).fetchone()
        self.assertEqual(qty, "3")
        self.assertEqual(status, "Active")

        billing_root.destroy()

        sales_root = self.make_root()
        sales_window = sales.salesClass(sales_root)
        sales_root.update_idletasks()
        invoice_name = f"{invoice_id}.txt"
        files = sales_window.Sales_List.get(0, END)
        self.assertIn(invoice_name, files)
        target_index = files.index(invoice_name)
        sales_window.Sales_List.selection_clear(0, END)
        sales_window.Sales_List.selection_set(target_index)
        sales_window.get_data(None)
        bill_text = sales_window.bill_area.get("1.0", END)
        self.assertIn(invoice_id, bill_text)


class RegressionTests(IntegrationTestCase):
    """Task T3 regression coverage to guard low-stock behaviors."""

    def _insert_products(self, rows):
        with closing(sqlite3.connect(DB_PATH)) as con:
            cur = con.cursor()
            cur.executemany(
                "insert into product(Category,Supplier,name,price,qty,status) values (?,?,?,?,?,?)",
                rows,
            )
            con.commit()

    def test_threshold_save_updates_dashboard_and_product_banner(self):
        custom_threshold = 9
        low_stock.set_low_stock_threshold(custom_threshold)
        low_stock.reset_cached_threshold()
        sample_products = [
            ("Phones", "ACME", "Phone Mini", "199", "2", "Active"),
            ("Phones", "ACME", "Phone Plus", "249", "9", "Active"),
            ("Audio", "ACME", "Speaker Pro", "149", "11", "Active"),
        ]
        self._insert_products(sample_products)

        product_root = self.make_root()
        product_window = product.productClass(product_root)
        product_root.update_idletasks()
        expected_banner = "Low stock threshold: 9 units | 2 product(s) need restocking"
        self.assertEqual(product_window.lbl_low_stock_hint.cget("text"), expected_banner)
        self._safe_destroy(product_root)

        dashboard_root = self.make_root()
        dashboard_window = dashboard.IMS(dashboard_root)
        dashboard_root.update_idletasks()
        expected_kpi = "Low Stock (<= 9)\n[ 2 ]"
        self.assertEqual(dashboard_window.lbl_low_stock.cget("text"), expected_kpi)
        self._safe_destroy(dashboard_root)

    def test_deleting_product_preserves_cached_threshold(self):
        custom_threshold = 6
        low_stock.set_low_stock_threshold(custom_threshold)
        low_stock.reset_cached_threshold()
        product_row = ("Phones", "ACME", "Legacy Speaker", "99", "3", "Active")
        with closing(sqlite3.connect(DB_PATH)) as con:
            cur = con.cursor()
            cur.execute(
                "insert into product(Category,Supplier,name,price,qty,status) values (?,?,?,?,?,?)",
                product_row,
            )
            pid = cur.lastrowid
            con.commit()

        product_root = self.make_root()
        product_window = product.productClass(product_root)
        product_root.update_idletasks()
        product_window.var_pid.set(str(pid))
        product_window.delete()
        low_stock.reset_cached_threshold()
        self.assertEqual(low_stock.get_low_stock_threshold(), custom_threshold)
        expected_banner = "Low stock threshold: 6 units | All listed products are above the alert level"
        self.assertEqual(product_window.lbl_low_stock_hint.cget("text"), expected_banner)
        self._safe_destroy(product_root)


if __name__ == "__main__":
    unittest.main()
