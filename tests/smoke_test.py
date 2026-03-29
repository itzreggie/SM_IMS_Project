"""GUI smoke test suite for the Inventory Management System."""
import importlib
import os
import shutil
import sqlite3
import sys
import uuid
from pathlib import Path
from tkinter import Tk

BASE_DIR = Path(__file__).resolve().parent.parent
os.chdir(BASE_DIR)
sys.path.insert(0,str(BASE_DIR))

TABLES = ("employee","supplier","category","product")
GUI_TARGETS = (
    ("dashboard","IMS"),
    ("employee","employeeClass"),
    ("supplier","supplierClass"),
    ("category","categoryClass"),
    ("product","productClass"),
    ("sales","salesClass"),
    ("billing","billClass"),
    ("low_stock","lowStockClass"),
)
LEGACY_FOLDER_NAME = "Inventory-Management-System"
SMOKE_INVOICE_NAME = "SMOKE_TEST_INVOICE.txt"
POST_INIT_METHODS = {
    "employee.employeeClass": ("show",),
    "supplier.supplierClass": ("show",),
    "category.categoryClass": ("show",),
    "product.productClass": ("show",),
    "sales.salesClass": ("show",),
    "billing.billClass": ("show",),
    "low_stock.lowStockClass": ("refresh_data",),
}
POST_INIT_CHECKS = {}
MODULE_VALIDATION_LABELS = {
    "sales.salesClass":"sales",
}


def ensure_database():
    import create_db

    create_db.create_db()
    with sqlite3.connect(BASE_DIR / "ims.db") as con:
        for table in TABLES:
            con.execute(f"select 1 from {table} limit 1")


def _ensure(condition,message):
    if not condition:
        raise RuntimeError(message)


def instantiate_gui(module_name,class_name,extra_methods=(),extra_checks=()):
    module=importlib.import_module(module_name)
    gui_cls=getattr(module,class_name)
    root=Tk()
    root.withdraw()
    try:
        instance=gui_cls(root)
        root.update_idletasks()
        for method_name in extra_methods:
            getattr(instance,method_name)()
        for check in extra_checks:
            check(instance)
    finally:
        root.destroy()


def seed_bill_directory():
    bill_dir=BASE_DIR/"bill"
    bill_dir.mkdir(exist_ok=True)
    sample_bill=bill_dir/SMOKE_INVOICE_NAME
    if not sample_bill.exists():
        sample_bill.write_text("Invoice: SMOKE_TEST\nTotal: 0\n",encoding="utf-8")
    return sample_bill


def _verify_sales_invoice_list(instance):
    files=instance.Sales_List.get(0,"end")
    _ensure(files,"Sales list is empty")
    _ensure(
        any(name==SMOKE_INVOICE_NAME for name in files),
        "Sales module did not surface the smoke invoice",
    )


POST_INIT_CHECKS["sales.salesClass"]=( _verify_sales_invoice_list,)


def crud_employee(cur,marker):
    email=f"smoke_{marker}@example.com"
    contact=f"555{marker[:7]}"
    cur.execute(
        """
        insert into employee(name,email,gender,contact,dob,doj,pass,utype,address,salary)
        values (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            f"Smoke Tester {marker}",
            email,
            "Male",
            contact,
            "1990-01-01",
            "2020-01-01",
            "testpass",
            "Admin",
            "Smoke Address",
            "50000",
        ),
    )
    _ensure(cur.rowcount==1,"Failed to insert employee fixture")
    row=cur.execute("select salary from employee where email=?",(email,)).fetchone()
    _ensure(row and row[0]=="50000","Employee insert verification failed")
    cur.execute("update employee set salary=? where email=?",("52000",email))
    row=cur.execute("select salary from employee where email=?",(email,)).fetchone()
    _ensure(row and row[0]=="52000","Employee update verification failed")
    cur.execute("delete from employee where email=?",(email,))
    _ensure(cur.rowcount==1,"Failed to delete employee fixture")
    return "employee"


def crud_category(cur,marker):
    name=f"{marker}_Category"
    cur.execute("insert into category(name) values (?)",(name,))
    cid=cur.lastrowid
    _ensure(cid is not None,"Failed to insert category fixture")
    row=cur.execute("select name from category where cid=?",(cid,)).fetchone()
    _ensure(row and row[0]==name,"Category insert verification failed")
    new_name=f"{name}_Updated"
    cur.execute("update category set name=? where cid=?",(new_name,cid))
    row=cur.execute("select name from category where cid=?",(cid,)).fetchone()
    _ensure(row and row[0]==new_name,"Category update verification failed")
    return cid,new_name,"category"


def cleanup_category(cur,cid):
    if cid is None:
        return
    cur.execute("delete from category where cid=?",(cid,))
    _ensure(cur.rowcount==1,"Failed to clean up category fixture")


def crud_supplier(cur,marker):
    name=f"{marker}_Supplier"
    contact=f"777{marker[:7]}"
    cur.execute(
        "insert into supplier(name,contact,\"desc\") values (?,?,?)",
        (name,contact,"Smoke supplier"),
    )
    invoice=cur.lastrowid
    _ensure(invoice is not None,"Failed to insert supplier fixture")
    row=cur.execute("select contact from supplier where invoice=?",(invoice,)).fetchone()
    _ensure(row and row[0]==contact,"Supplier insert verification failed")
    new_contact=f"888{marker[:7]}"
    cur.execute(
        "update supplier set contact=?, \"desc\"=? where invoice=?",
        (new_contact,"Updated smoke supplier",invoice),
    )
    row=cur.execute(
        "select contact,\"desc\" from supplier where invoice=?",(invoice,)
    ).fetchone()
    _ensure(row and row[0]==new_contact,"Supplier update verification failed")
    return invoice,name,"supplier"


def cleanup_supplier(cur,invoice):
    if invoice is None:
        return
    cur.execute("delete from supplier where invoice=?",(invoice,))
    _ensure(cur.rowcount==1,"Failed to clean up supplier fixture")


def crud_product(cur,marker,category_name,supplier_name):
    pid=None
    try:
        name=f"{marker}_Product"
        cur.execute(
            """
            insert into product(Category,Supplier,name,price,qty,status)
            values (?,?,?,?,?,?)
            """,
            (category_name,supplier_name,name,"10","5","Active"),
        )
        pid=cur.lastrowid
        _ensure(pid is not None,"Failed to insert product fixture")
        row=cur.execute("select qty from product where pid=?",(pid,)).fetchone()
        _ensure(row and row[0]=="5","Product insert verification failed")
        cur.execute(
            "update product set price=?, qty=?, status=? where pid=?",
            ("12","3","Inactive",pid),
        )
        row=cur.execute(
            "select price,qty,status from product where pid=?",
            (pid,),
        ).fetchone()
        _ensure(
            row and row[0]=="12" and row[1]=="3" and row[2]=="Inactive",
            "Product update verification failed",
        )
        cur.execute("delete from product where pid=?",(pid,))
        _ensure(cur.rowcount==1,"Failed to delete product fixture")
    except Exception:
        if pid is not None:
            cur.execute("delete from product where pid=?",(pid,))
        raise
    return "product"


def perform_crud_checks():
    marker=uuid.uuid4().hex[:8]
    tested=[]
    cat_id=supplier_id=None
    with sqlite3.connect(BASE_DIR / "ims.db") as con:
        cur=con.cursor()
        tested.append(crud_employee(cur,marker))
        try:
            cat_id,category_name,cat_label=crud_category(cur,marker)
            tested.append(cat_label)
            supplier_id,supplier_name,sup_label=crud_supplier(cur,marker)
            tested.append(sup_label)
            tested.append(crud_product(cur,marker,category_name,supplier_name))
        finally:
            cleanup_supplier(cur,supplier_id)
            cleanup_category(cur,cat_id)
    return tested

def prepare_legacy_assets():
    legacy_dir=BASE_DIR/LEGACY_FOLDER_NAME
    images_src=BASE_DIR/"images"
    if not images_src.exists():
        return
    legacy_images=legacy_dir/"images"
    legacy_images.mkdir(parents=True,exist_ok=True)
    for image in images_src.iterdir():
        if image.is_file():
            target=legacy_images/image.name
            if not target.exists() or image.stat().st_mtime>target.stat().st_mtime:
                shutil.copy2(image,target)


def main():
    ensure_database()
    os.makedirs(BASE_DIR / "bill",exist_ok=True)
    seed_bill_directory()
    crud_entities=perform_crud_checks()
    prepare_legacy_assets()
    succeeded=[]
    module_validations=[]
    for module_name,class_name in GUI_TARGETS:
        qual_name=f"{module_name}.{class_name}"
        methods=POST_INIT_METHODS.get(qual_name,())
        checks=POST_INIT_CHECKS.get(qual_name,())
        instantiate_gui(module_name,class_name,methods,checks)
        succeeded.append(qual_name)
        label=MODULE_VALIDATION_LABELS.get(qual_name)
        if label:
            module_validations.append(label)
    verified_targets=crud_entities+module_validations
    print("CRUD/file fixtures verified: "+", ".join(verified_targets))
    print("Smoke test finished: "+", ".join(succeeded))


if __name__=="__main__":
    main()
