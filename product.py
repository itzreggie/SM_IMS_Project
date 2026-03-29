from tkinter import*
from PIL import Image,ImageTk
from tkinter import ttk,messagebox
import sqlite3
from contextlib import closing

from low_stock import get_low_stock_threshold

class productClass:
    def __init__(self,root):
        self.root=root
        self.root.geometry("1100x500+320+220")
        self.root.config(bg="white")
        self.root.resizable(False,False)
        self.root.focus_force()
        #---------------------------------------
        #----------- variables -------------
        self.var_cat=StringVar()
        self.cat_list=[]
        self.sup_list=[]
        self.fetch_cat_sup()
        self.var_pid=StringVar()
        self.var_sup=StringVar()
        self.var_name=StringVar()
        self.var_price=StringVar()
        self.var_qty=StringVar()
        self.var_status=StringVar()
        self.var_searchby=StringVar()
        self.var_searchtxt=StringVar()

        product_Frame=Frame(self.root,bd=2,relief=RIDGE,bg="white")
        product_Frame.place(x=10,y=10,width=450,height=480)

        #------------ title --------------
        title=Label(product_Frame,text="Manage Product Details",font=("goudy old style",18),bg="#0f4d7d",fg="white").pack(side=TOP,fill=X)

        lbl_category=Label(product_Frame,text="Category",font=("goudy old style",18),bg="white").place(x=30,y=60)
        lbl_supplier=Label(product_Frame,text="Supplier",font=("goudy old style",18),bg="white").place(x=30,y=110)
        lbl_product_name=Label(product_Frame,text="Name",font=("goudy old style",18),bg="white").place(x=30,y=160)
        lbl_price=Label(product_Frame,text="Price",font=("goudy old style",18),bg="white").place(x=30,y=210)
        lbl_qty=Label(product_Frame,text="Quantity",font=("goudy old style",18),bg="white").place(x=30,y=260)
        lbl_status=Label(product_Frame,text="Status",font=("goudy old style",18),bg="white").place(x=30,y=310)

        # EDITED: Keeping combobox handles so their option lists can be refreshed after DB sync.
        self.cmb_cat=ttk.Combobox(product_Frame,textvariable=self.var_cat,values=self.cat_list,state='readonly',justify=CENTER,font=("goudy old style",15))
        self.cmb_cat.place(x=150,y=60,width=200)
        self.cmb_cat.current(0)

        self.cmb_sup=ttk.Combobox(product_Frame,textvariable=self.var_sup,values=self.sup_list,state='readonly',justify=CENTER,font=("goudy old style",15))
        self.cmb_sup.place(x=150,y=110,width=200)
        self.cmb_sup.current(0)

        txt_name=Entry(product_Frame,textvariable=self.var_name,font=("goudy old style",15),bg="lightyellow").place(x=150,y=160,width=200)
        txt_price=Entry(product_Frame,textvariable=self.var_price,font=("goudy old style",15),bg="lightyellow").place(x=150,y=210,width=200)
        txt_qty=Entry(product_Frame,textvariable=self.var_qty,font=("goudy old style",15),bg="lightyellow").place(x=150,y=260,width=200)

        cmb_status=ttk.Combobox(product_Frame,textvariable=self.var_status,values=("Active","Inactive"),state='readonly',justify=CENTER,font=("goudy old style",15))
        cmb_status.place(x=150,y=310,width=200)
        cmb_status.current(0)

        #-------------- buttons -----------------
        btn_add=Button(product_Frame,text="Save",command=self.add,font=("goudy old style",15),bg="#2196f3",fg="white",cursor="hand2").place(x=10,y=400,width=100,height=40)
        btn_update=Button(product_Frame,text="Update",command=self.update,font=("goudy old style",15),bg="#4caf50",fg="white",cursor="hand2").place(x=120,y=400,width=100,height=40)
        btn_delete=Button(product_Frame,text="Delete",command=self.delete,font=("goudy old style",15),bg="#f44336",fg="white",cursor="hand2").place(x=230,y=400,width=100,height=40)
        btn_clear=Button(product_Frame,text="Clear",command=self.clear,font=("goudy old style",15),bg="#607d8b",fg="white",cursor="hand2").place(x=340,y=400,width=100,height=40)

        #---------- Search Frame -------------
        SearchFrame=LabelFrame(self.root,text="Search Product",font=("goudy old style",12,"bold"),bd=2,relief=RIDGE,bg="white")
        SearchFrame.place(x=480,y=10,width=600,height=80)

        #------------ options ----------------
        cmb_search=ttk.Combobox(SearchFrame,textvariable=self.var_searchby,values=("Select","Category","Supplier","Name"),state='readonly',justify=CENTER,font=("goudy old style",15))
        cmb_search.place(x=10,y=10,width=180)
        cmb_search.current(0)

        txt_search=Entry(SearchFrame,textvariable=self.var_searchtxt,font=("goudy old style",15),bg="lightyellow").place(x=200,y=10)
        btn_search=Button(SearchFrame,text="Search",command=self.search,font=("goudy old style",15),bg="#4caf50",fg="white",cursor="hand2").place(x=410,y=9,width=150,height=30)

        self.lbl_low_stock_hint=Label(SearchFrame,text="",font=("goudy old style",12),bg="white",fg="#bf360c",anchor="w")
        self.lbl_low_stock_hint.place(x=10,y=45,width=560)

        #------------ product details -------------
        product_frame=Frame(self.root,bd=3,relief=RIDGE)
        product_frame.place(x=480,y=100,width=600,height=390)

        scrolly=Scrollbar(product_frame,orient=VERTICAL)
        scrollx=Scrollbar(product_frame,orient=HORIZONTAL)\
        
        self.ProductTable=ttk.Treeview(product_frame,columns=("pid","Category","Supplier","name","price","qty","status"),yscrollcommand=scrolly.set,xscrollcommand=scrollx.set)
        scrollx.pack(side=BOTTOM,fill=X)
        scrolly.pack(side=RIGHT,fill=Y)
        scrollx.config(command=self.ProductTable.xview)
        scrolly.config(command=self.ProductTable.yview)
        self.ProductTable.heading("pid",text="P ID")
        self.ProductTable.heading("Category",text="Category")
        self.ProductTable.heading("Supplier",text="Suppler")
        self.ProductTable.heading("name",text="Name")
        self.ProductTable.heading("price",text="Price")
        self.ProductTable.heading("qty",text="Quantity")
        self.ProductTable.heading("status",text="Status")
        self.ProductTable["show"]="headings"
        self.ProductTable.column("pid",width=90)
        self.ProductTable.column("Category",width=100)
        self.ProductTable.column("Supplier",width=100)
        self.ProductTable.column("name",width=100)
        self.ProductTable.column("price",width=100)
        self.ProductTable.column("qty",width=100)
        self.ProductTable.column("status",width=100)

        self.ProductTable.tag_configure("low_stock",background="#fff4dd")
        self.ProductTable.pack(fill=BOTH,expand=1)
        self.ProductTable.bind("<ButtonRelease-1>",self.get_data)
        self.show()
        self.fetch_cat_sup()
#-----------------------------------------------------------------------------------------------------
    # EDITED: Reworked dropdown loading to reuse the query helper and keep selections in sync.
    def fetch_cat_sup(self):
        try:
            cat=self._run_query("select name from category",fetch="all") or []
            sup=self._run_query("select name from supplier",fetch="all") or []
            self.cat_list=["Select"]+[i[0] for i in cat] if cat else ["Empty"]
            self.sup_list=["Select"]+[i[0] for i in sup] if sup else ["Empty"]
            if hasattr(self,'cmb_cat'):
                self.cmb_cat.config(values=self.cat_list)
                self.cmb_cat.current(0)
            if hasattr(self,'cmb_sup'):
                self.cmb_sup.config(values=self.sup_list)
                self.cmb_sup.current(0)
        except Exception as ex:
            messagebox.showerror("Error",f"Error due to : {str(ex)}")

    
    
    # EDITED: Added stricter validation and duplicate checks before inserting a product.
    def add(self):
        try:
            if self.var_cat.get() in ("Select","Empty") or self.var_sup.get() in ("Select","Empty"):
                messagebox.showerror("Error","All fields are required",parent=self.root)
                return
            if any(not value.strip() for value in (self.var_name.get(),self.var_price.get(),self.var_qty.get())):
                messagebox.showerror("Error","Name, price and quantity are required",parent=self.root)
                return
            row=self._run_query("Select * from product where name=?",(self.var_name.get().strip(),),fetch="one")
            if row:
                messagebox.showerror("Error","Product already present",parent=self.root)
                return
            self._run_query("insert into product(Category,Supplier,name,price,qty,status) values(?,?,?,?,?,?)",(
                self.var_cat.get(),
                self.var_sup.get(),
                self.var_name.get().strip(),
                self.var_price.get().strip(),
                self.var_qty.get().strip(),
                self.var_status.get(),
            ))
            messagebox.showinfo("Success","Product Added Successfully",parent=self.root)
            self.clear()
            self.show()
        except Exception as ex:
            messagebox.showerror("Error",f"Error due to : {str(ex)}")

    # EDITED: Pulling rows through the shared query helper to keep DB access uniform.
    def show(self):
        try:
            rows=self._run_query("select * from product",fetch="all") or []
            self._refresh_product_table(rows)
        except Exception as ex:
            messagebox.showerror("Error",f"Error due to : {str(ex)}")

    # EDITED: Guard clause avoids crashes when the treeview sends an empty selection.
    def get_data(self,ev):
        f=self.ProductTable.focus()
        content=(self.ProductTable.item(f))
        row=content['values']
        if not row:
            return
        self.var_pid.set(row[0])
        self.var_cat.set(row[1])
        self.var_sup.set(row[2])
        self.var_name.set(row[3])
        self.var_price.set(row[4])
        self.var_qty.set(row[5])
        self.var_status.set(row[6])

    # EDITED: Consolidated lookups and updates through the helper for cleaner logic.
    def update(self):
        try:
            if self.var_pid.get()=="":
                messagebox.showerror("Error","Please select product from list",parent=self.root)
                return
            row=self._run_query("Select * from product where pid=?",(self.var_pid.get(),),fetch="one")
            if row is None:
                messagebox.showerror("Error","Invalid Product",parent=self.root)
                return
            self._run_query("update product set Category=?,Supplier=?,name=?,price=?,qty=?,status=? where pid=?",(
                self.var_cat.get(),
                self.var_sup.get(),
                self.var_name.get(),
                self.var_price.get(),
                self.var_qty.get(),
                self.var_status.get(),
                self.var_pid.get(),
            ))
            messagebox.showinfo("Success","Product Updated Successfully",parent=self.root)
            self.show()
        except Exception as ex:
            messagebox.showerror("Error",f"Error due to : {str(ex)}")

    # EDITED: Using the helper for verification plus early returns for clearer flow.
    def delete(self):
        try:
            if self.var_pid.get()=="":
                messagebox.showerror("Error","Select Product from the list",parent=self.root)
                return
            row=self._run_query("Select * from product where pid=?",(self.var_pid.get(),),fetch="one")
            if row is None:
                messagebox.showerror("Error","Invalid Product",parent=self.root)
                return
            op=messagebox.askyesno("Confirm","Do you really want to delete?",parent=self.root)
            if op:
                self._run_query("delete from product where pid=?",(self.var_pid.get(),))
                messagebox.showinfo("Delete","Product Deleted Successfully",parent=self.root)
                self.clear()
        except Exception as ex:
            messagebox.showerror("Error",f"Error due to : {str(ex)}")

    def clear(self):
        self.var_cat.set("Select")
        self.var_sup.set("Select")
        self.var_name.set("")
        self.var_price.set("")
        self.var_qty.set("")
        self.var_status.set("Active")
        self.var_pid.set("")
        self.var_searchby.set("Select")
        self.var_searchtxt.set("")
        self.show()

    
    # EDITED: Parameterized the search to prevent string concatenation bugs and SQL injection.
    def search(self):
        try:
            search_by=self.var_searchby.get()
            search_txt=self.var_searchtxt.get().strip()
            column_map={
                "Category":"Category",
                "Supplier":"Supplier",
                "Name":"name"
            }
            column=column_map.get(search_by)
            if not column:
                messagebox.showerror("Error","Select Search By option",parent=self.root)
                return
            if not search_txt:
                messagebox.showerror("Error","Search input should be required",parent=self.root)
                return
            rows=self._run_query(f"select * from product where {column} LIKE ?",(f"%{search_txt}%",),fetch="all") or []
            if rows:
                self._refresh_product_table(rows)
            else:
                self._refresh_product_table([])
                messagebox.showerror("Error","No record found!!!",parent=self.root)
        except Exception as ex:
            messagebox.showerror("Error",f"Error due to : {str(ex)}")

    # EDITED: Added a tiny wrapper so all SQL goes through one well-tested path.
    def _run_query(self,query,params=(),fetch=None):
        with closing(sqlite3.connect(database=r'ims.db')) as con:
            cur=con.cursor()
            cur.execute(query,params)
            if fetch=="one":
                return cur.fetchone()
            if fetch=="all":
                return cur.fetchall()
            con.commit()

    # EDITED: Centralized the table painting so every caller refreshes the same way.
    def _refresh_product_table(self,rows):
        threshold=get_low_stock_threshold()
        low_stock_rows=0
        self.ProductTable.delete(*self.ProductTable.get_children())
        for row in rows:
            qty_value=self._safe_qty_value(row[5])
            tags=()
            if qty_value is not None and qty_value<=threshold:
                tags=("low_stock",)
                low_stock_rows+=1
            self.ProductTable.insert('',END,values=row,tags=tags)
        banner_text=f"Low stock threshold: {threshold} units"
        if low_stock_rows:
            banner_text+=f" | {low_stock_rows} product(s) need restocking"
        else:
            banner_text+=" | All listed products are above the alert level"
        self.lbl_low_stock_hint.config(text=banner_text)

    def _safe_qty_value(self,value):
        try:
            qty=int(str(value).strip())
        except (TypeError,ValueError):
            return None
        return max(0,qty)

if __name__=="__main__":
    root=Tk()
    obj=productClass(root)
    root.mainloop()