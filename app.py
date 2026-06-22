import sqlite3
import json
import re
import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk, ImageGrab
import piexif
from fractions import Fraction
from tkinterdnd2 import TkinterDnD, DND_FILES
import urllib.request
import ssl
import threading
import sys
import subprocess

ctk.set_appearance_mode("Dark")  
ctk.set_default_color_theme("dark-blue")  

DB_PATH = 'store_profiles.db'

def create_connection():
    try:
        # Lấy thư mục chứa file chạy (để hỗ trợ exe chạy ngầm)
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        db_file = os.path.join(base_dir, DB_PATH)
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Bảng Settings
        cursor.execute('''CREATE TABLE IF NOT EXISTS app_settings (
                            key TEXT PRIMARY KEY, 
                            value TEXT)''')
                            
        # Khởi tạo settings mặc định nếu chưa có
        default_settings = {
            'app_name': 'td geo tag',
            'app_version': '1.0.0',
            'logo_path': '',
            'github_repo': ''
        }
        for k, v in default_settings.items():
            cursor.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)", (k, v))
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS categories (
                            id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            name TEXT UNIQUE NOT NULL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS stores (
                            id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            name TEXT NOT NULL, 
                            category_id INTEGER, 
                            tags TEXT, 
                            address TEXT, 
                            phone TEXT, 
                            website TEXT, 
                            latitude REAL, 
                            longitude REAL, 
                            FOREIGN KEY (category_id) REFERENCES categories (id))''')
        
        # Cập nhật 'nails' thành 'nail salon' một cách an toàn
        cursor.execute("SELECT id FROM categories WHERE name COLLATE NOCASE = 'nails'")
        old_cat = cursor.fetchone()
        if old_cat:
            old_id = old_cat[0]
            cursor.execute("SELECT id FROM categories WHERE name COLLATE NOCASE = 'nail salon'")
            new_cat = cursor.fetchone()
            if new_cat:
                new_id = new_cat[0]
                cursor.execute("UPDATE stores SET category_id = ? WHERE category_id = ?", (new_id, old_id))
                cursor.execute("DELETE FROM categories WHERE id = ?", (old_id,))
            else:
                cursor.execute("UPDATE categories SET name = 'nail salon' WHERE id = ?", (old_id,))
        
        conn.commit()
        return conn
    except Exception as e:
        messagebox.showerror("Lỗi", f"Không thể kết nối DB: {e}")
        return None

def get_settings():
    conn = create_connection()
    if not conn: return {}
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM app_settings")
    settings = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return settings

def set_setting(key, value):
    conn = create_connection()
    if not conn: return
    cur = conn.cursor()
    cur.execute("UPDATE app_settings SET value = ? WHERE key = ?", (value, key))
    conn.commit()
    conn.close()

def to_deg(value, loc):
    if value < 0: loc_value = loc[0]
    elif value > 0: loc_value = loc[1]
    else: loc_value = ""
    abs_value = abs(value)
    deg = int(abs_value)
    t1 = (abs_value-deg)*60
    min = int(t1)
    sec = round((t1 - min)* 60, 5)
    return (deg, min, sec, loc_value)

def change_to_rational(number):
    f = Fraction(str(number)).limit_denominator()
    return (f.numerator, f.denominator)

def set_gps_location(file_path, lat, lng, store_info, output_path):
    try:
        img = Image.open(file_path)
        if "exif" in img.info:
            exif_dict = piexif.load(img.info["exif"])
        else:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}}
        
        if store_info:
            if store_info.get("name"): exif_dict["0th"][piexif.ImageIFD.XPTitle] = store_info["name"].encode("utf-16le")
            if store_info.get("category"): exif_dict["0th"][piexif.ImageIFD.XPSubject] = store_info["category"].encode("utf-16le")
            if store_info.get("tags"): exif_dict["0th"][piexif.ImageIFD.XPKeywords] = store_info["tags"].encode("utf-16le")
            
            addr = store_info.get('address', '')
            phone = store_info.get('phone', '')
            website = store_info.get('website', '')
            comments = f"{addr} | {phone}: {website}"
            exif_dict["0th"][piexif.ImageIFD.XPComment] = comments.encode("utf-16le")
            exif_dict["0th"][piexif.ImageIFD.Rating] = 5
            
            if website:
                exif_dict["0th"][piexif.ImageIFD.XPAuthor] = website.encode("utf-16le")
                exif_dict["0th"][piexif.ImageIFD.Copyright] = website.encode("ascii")
        
        lat_deg = to_deg(lat, ["S", "N"])
        lng_deg = to_deg(lng, ["W", "E"])
        
        exif_dict["GPS"][piexif.GPSIFD.GPSVersionID] = (2, 2, 0, 0)
        exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = lat_deg[3].encode('ascii')
        exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = [change_to_rational(lat_deg[0]), change_to_rational(lat_deg[1]), change_to_rational(lat_deg[2])]
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = lng_deg[3].encode('ascii')
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = [change_to_rational(lng_deg[0]), change_to_rational(lng_deg[1]), change_to_rational(lng_deg[2])]
        
        exif_bytes = piexif.dump(exif_dict)
        img.save(output_path, "jpeg", exif=exif_bytes)
        return True
    except Exception as e:
        print(f"Lỗi Geo-tag file {file_path}: {e}")
        return False

def check_has_gps(file_path):
    try:
        img = Image.open(file_path)
        if "exif" in img.info:
            exif_dict = piexif.load(img.info["exif"])
            if "GPS" in exif_dict and piexif.GPSIFD.GPSLatitude in exif_dict["GPS"]:
                return True
    except Exception:
        pass
    return False

class Tk(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)

class App(Tk):
    def __init__(self):
        super().__init__()
        
        # Load Settings
        self.settings = get_settings()
        app_name = self.settings.get('app_name', 'Geo-Tag Tiệm')
        app_version = self.settings.get('app_version', '1.0.0')
        logo_path = self.settings.get('app_logo', '')
        
        self.title(f"{app_name} v{app_version}")
        self.geometry("1200x800")
        
        # Thiết lập icon nếu có
        if logo_path and os.path.exists(logo_path) and logo_path.endswith('.ico'):
            try:
                self.iconbitmap(logo_path)
            except Exception:
                pass
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.current_store_id = None
        self.image_paths = []
        self.current_image_index = -1
        
        self.bind("<Control-v>", self.paste_image)
        self.bind("<Control-V>", self.paste_image)
        
        self.setup_left_panel()
        self.setup_right_panel()
        self.load_categories()
        self.load_store_list()
        
        # Chạy kiểm tra bản cập nhật
        self.after(1000, self.check_for_updates)
        
    def setup_left_panel(self):
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        
        # Khung chứa header (Admin btn và Title)
        header_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(header_frame, text="⚙️ Admin", width=60, fg_color="#444", hover_color="#222", command=self.admin_login).grid(row=0, column=0, sticky="w")
        
        search_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        search_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(search_frame, text="Lọc/Tìm:").grid(row=0, column=0, sticky="w")
        
        self.filter_cat_combo = ctk.CTkComboBox(search_frame, values=["Tất cả loại"], command=self.filter_stores)
        self.filter_cat_combo.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.filter_cat_combo.set("Tất cả loại") # Fix lỗi hiển thị CTkComboBox
        
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Tên tiệm...")
        self.search_entry.grid(row=0, column=2, sticky="ew", padx=(10, 0))
        self.search_entry.bind("<KeyRelease>", self.filter_stores)
        
        self.store_list_frame = ctk.CTkScrollableFrame(left_frame, label_text="Danh Sách Tiệm", height=200)
        self.store_list_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 20))
        
        # Form nhập liệu
        form_frame = ctk.CTkFrame(left_frame, fg_color="#2b2b2b")
        form_frame.grid(row=3, column=0, sticky="ew", ipadx=10, ipady=10)
        form_frame.grid_columnconfigure(1, weight=1)
        
        fields = [
            ("Loại tiệm *:", "category"),
            ("Tên tiệm *:", "name"),
            ("Tags (ngăn cách dấu ,):", "tags"),
            ("Địa chỉ *:", "address"),
            ("SĐT *:", "phone"),
            ("Website:", "website"),
            ("Google Maps URL:", "gg_maps")
        ]
        
        self.entries = {}
        row_idx = 0
        for label_text, key in fields:
            ctk.CTkLabel(form_frame, text=label_text).grid(row=row_idx, column=0, sticky="w", pady=5, padx=10)
            if key == "category":
                cat_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
                cat_frame.grid(row=row_idx, column=1, sticky="ew", pady=5, padx=(10, 10))
                cat_frame.grid_columnconfigure(0, weight=1)
                
                self.category_combo = ctk.CTkComboBox(cat_frame, values=[])
                self.category_combo.grid(row=0, column=0, sticky="ew")
                self.category_combo.set("") # Fix lỗi hiển thị CTkComboBox
                self.entries[key] = self.category_combo
                
                btn_cat_mgr = ctk.CTkButton(cat_frame, text="Quản Lý", width=60, fg_color="#444", command=self.open_category_manager)
                btn_cat_mgr.grid(row=0, column=1, padx=(5, 0))
            elif key == "gg_maps":
                frame_gg = ctk.CTkFrame(form_frame, fg_color="transparent")
                frame_gg.grid(row=row_idx, column=1, sticky="ew", pady=5, padx=(10, 10))
                frame_gg.grid_columnconfigure(0, weight=1)
                self.entries[key] = ctk.CTkEntry(frame_gg)
                self.entries[key].grid(row=0, column=0, sticky="ew")
                btn_get_coords = ctk.CTkButton(frame_gg, text="Lấy Tọa Độ", width=80, command=self.extract_coordinates)
                btn_get_coords.grid(row=0, column=1, padx=(5, 0))
            else:
                entry = ctk.CTkEntry(form_frame)
                entry.grid(row=row_idx, column=1, sticky="ew", pady=5, padx=(10, 10))
                self.entries[key] = entry
            row_idx += 1
            
        ctk.CTkLabel(form_frame, text="Tọa độ:").grid(row=row_idx, column=0, sticky="w", pady=5, padx=10)
        coord_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        coord_frame.grid(row=row_idx, column=1, sticky="ew", pady=5, padx=(10, 10))
        coord_frame.grid_columnconfigure((0, 1), weight=1)
        self.lat_entry = ctk.CTkEntry(coord_frame, placeholder_text="Latitude")
        self.lat_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.lng_entry = ctk.CTkEntry(coord_frame, placeholder_text="Longitude")
        self.lng_entry.grid(row=0, column=1, sticky="ew")
        
        btn_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_frame.grid(row=row_idx+1, column=0, columnspan=2, pady=(15, 0), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        ctk.CTkButton(btn_frame, text="Thêm Mới", fg_color="#333", border_width=1, border_color="#555", command=self.save_store).grid(row=0, column=0, padx=5, sticky="ew")
        ctk.CTkButton(btn_frame, text="Cập Nhật", fg_color="#333", border_width=1, border_color="#555", command=self.update_store).grid(row=0, column=1, padx=5, sticky="ew")
        ctk.CTkButton(btn_frame, text="Xóa", fg_color="#b32d2d", hover_color="#8f2424", command=self.delete_store).grid(row=0, column=2, padx=5, sticky="ew")
        ctk.CTkButton(btn_frame, text="Làm Mới Form", fg_color="#333", border_width=1, border_color="#555", command=self.clear_form).grid(row=0, column=3, padx=5, sticky="ew")
        
        ctk.CTkButton(left_frame, text="Thêm hàng loạt từ JSON", fg_color="#2d7ab3", hover_color="#24628f", command=self.open_json_dialog).grid(row=4, column=0, pady=(20, 0), sticky="ew")

    def setup_right_panel(self):
        right_frame = ctk.CTkFrame(self, fg_color="#222")
        right_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        
        self.add_img_btn = ctk.CTkButton(right_frame, text="Kéo thả ảnh vào đây\nHoặc click để chọn\n(Hỗ trợ Ctrl+V)", height=60, fg_color="#333", command=self.select_images)
        self.add_img_btn.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        
        self.add_img_btn.drop_target_register(DND_FILES)
        self.add_img_btn.dnd_bind('<<Drop>>', self.drop_images)
        
        self.image_canvas = tk.Canvas(right_frame, bg="#111", highlightthickness=0)
        self.image_canvas.grid(row=1, column=0, padx=20, pady=0, sticky="nsew")
        self.image_canvas.bind("<Configure>", lambda e: self.update_image_preview())
        self.image_canvas.drop_target_register(DND_FILES)
        self.image_canvas.dnd_bind('<<Drop>>', self.drop_images)
        
        img_ctrl_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        img_ctrl_frame.grid(row=2, column=0, padx=20, pady=(20, 5), sticky="ew")
        img_ctrl_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(img_ctrl_frame, text="<", width=40, fg_color="#444", command=self.prev_image).grid(row=0, column=0)
        
        info_frame = ctk.CTkFrame(img_ctrl_frame, fg_color="transparent")
        info_frame.grid(row=0, column=1)
        self.lbl_image_count = ctk.CTkLabel(info_frame, text="0 / 0", font=("Arial", 12, "bold"))
        self.lbl_image_count.pack()
        self.lbl_gps_status = ctk.CTkLabel(info_frame, text="", font=("Arial", 10), text_color="gray")
        self.lbl_gps_status.pack()
        
        ctk.CTkButton(img_ctrl_frame, text=">", width=40, fg_color="#444", command=self.next_image).grid(row=0, column=2)
        ctk.CTkButton(img_ctrl_frame, text="Xóa ảnh", fg_color="#b32d2d", hover_color="#8f2424", command=self.remove_current_image).grid(row=0, column=3, padx=(10, 0))
        
        ctk.CTkButton(right_frame, text="XUẤT ẢNH GẮN TỌA ĐỘ", height=50, fg_color="#006400", hover_color="#008000", command=self.export_images).grid(row=3, column=0, padx=20, pady=(10, 20), sticky="ew")

    # ----- IMAGE LOGIC -----
    def paste_image(self, event=None):
        try:
            img = ImageGrab.grabclipboard()
            if img:
                if isinstance(img, list):
                    valid_files = [f for f in img if str(f).lower().endswith(('.jpg', '.jpeg'))]
                    if valid_files:
                        self.image_paths.extend(valid_files)
                        if self.current_image_index == -1: self.current_image_index = 0
                        self.update_image_preview()
                elif isinstance(img, Image.Image):
                    temp_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                    temp_path = os.path.join(temp_dir, f"Pasted_Image_{int(time.time())}.jpg")
                    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                    img.save(temp_path, "JPEG")
                    self.image_paths.append(temp_path)
                    if self.current_image_index == -1: self.current_image_index = 0
                    self.update_image_preview()
        except Exception:
            pass

    def drop_images(self, event):
        files = self.tk.splitlist(event.data)
        valid_files = [f for f in files if f.lower().endswith(('.jpg', '.jpeg'))]
        if valid_files:
            self.image_paths.extend(valid_files)
            if self.current_image_index == -1: self.current_image_index = 0
            self.update_image_preview()
        else:
            messagebox.showinfo("Chỉ hỗ trợ JPG", "Vui lòng kéo thả file JPG.")

    def select_images(self):
        files = filedialog.askopenfilenames(title="Chọn ảnh", filetypes=[("Image files", "*.jpg *.jpeg")])
        if files:
            self.image_paths.extend(files)
            if self.current_image_index == -1: self.current_image_index = 0
            self.update_image_preview()
            
    def update_image_preview(self):
        canvas_w = self.image_canvas.winfo_width()
        canvas_h = self.image_canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1: return
        
        self.image_canvas.delete("all")
        
        if not self.image_paths:
            self.image_canvas.create_text(canvas_w/2, canvas_h/2, text="Chưa Có Ảnh", fill="white", font=("Arial", 12))
            self.lbl_image_count.configure(text="0 / 0")
            self.lbl_gps_status.configure(text="")
            self.current_image_index = -1
            return
            
        img_path = self.image_paths[self.current_image_index]
        self.lbl_image_count.configure(text=f"{self.current_image_index + 1} / {len(self.image_paths)}")
        
        if check_has_gps(img_path):
            self.lbl_gps_status.configure(text="(Đã có tọa độ gốc)", text_color="#2E8B57")
        else:
            self.lbl_gps_status.configure(text="(Chưa có tọa độ)", text_color="gray")
        
        try:
            img = Image.open(img_path)
            img.thumbnail((canvas_w, canvas_h))
            self.tk_image = ImageTk.PhotoImage(img)
            self.image_canvas.create_image(canvas_w/2, canvas_h/2, anchor=tk.CENTER, image=self.tk_image)
        except Exception:
            self.image_canvas.create_text(canvas_w/2, canvas_h/2, text="Lỗi hiển thị ảnh", fill="red")
            
    def prev_image(self):
        if self.image_paths and self.current_image_index > 0:
            self.current_image_index -= 1
            self.update_image_preview()
            
    def next_image(self):
        if self.image_paths and self.current_image_index < len(self.image_paths) - 1:
            self.current_image_index += 1
            self.update_image_preview()
            
    def remove_current_image(self):
        if self.image_paths and self.current_image_index != -1:
            del self.image_paths[self.current_image_index]
            if self.current_image_index >= len(self.image_paths):
                self.current_image_index = len(self.image_paths) - 1
            self.update_image_preview()
            
    def export_images(self):
        if not self.image_paths:
            messagebox.showwarning("Lỗi", "Chưa có ảnh nào được tải vào.")
            return
        lat_str = self.lat_entry.get().strip()
        lng_str = self.lng_entry.get().strip()
        if not lat_str or not lng_str:
            messagebox.showwarning("Lỗi", "Chưa có tọa độ. Vui lòng lấy tọa độ của tiệm trước.")
            return
            
        try:
            lat = float(lat_str)
            lng = float(lng_str)
        except ValueError:
            messagebox.showerror("Lỗi", "Tọa độ không hợp lệ.")
            return
            
        store_name = self.entries["name"].get().strip()
        if not store_name: store_name = "Store"
            
        store_info = {
            "name": store_name,
            "category": self.category_combo.get().strip(),
            "tags": self.entries["tags"].get().strip(),
            "address": self.entries["address"].get().strip(),
            "phone": self.entries["phone"].get().strip(),
            "website": self.entries["website"].get().strip()
        }
            
        success_count = 0
        total_files = len(self.image_paths)
        
        for idx, path in enumerate(self.image_paths):
            folder = os.path.dirname(path)
            safe_name = re.sub(r'[\\/*?:"<>|]', "", store_name)
            if total_files == 1: new_filename = f"{safe_name}.jpg"
            else: new_filename = f"{safe_name}_{idx + 1}.jpg"
                
            new_path = os.path.join(folder, new_filename)
            if os.path.exists(new_path) and new_path != path:
                new_filename = f"{safe_name}_{idx + 1}_{int(time.time())}.jpg"
                new_path = os.path.join(folder, new_filename)
                
            if set_gps_location(path, lat, lng, store_info, new_path):
                if path != new_path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception: pass
                success_count += 1
                
        messagebox.showinfo("Thành công", f"Đã xuất và đổi tên thành công {success_count}/{total_files} ảnh!")
        self.image_paths.clear()
        self.update_image_preview()

    # ----- DB & FORM LOGIC -----
    def load_categories(self):
        conn = create_connection()
        if not conn: return
        cur = conn.cursor()
        cur.execute("SELECT name FROM categories ORDER BY name ASC")
        cats = [row[0] for row in cur.fetchall()]
        conn.close()
        
        current_val = self.category_combo.get()
        self.category_combo.configure(values=cats)
        if current_val not in cats: self.category_combo.set("")
        
        filter_cats = ["Tất cả loại"] + cats
        self.filter_cat_combo.configure(values=filter_cats)

    def load_store_list(self):
        for widget in self.store_list_frame.winfo_children(): widget.destroy()
        search_text = self.search_entry.get().strip()
        cat_filter = self.filter_cat_combo.get().strip()
        
        conn = create_connection()
        if not conn: return
        cur = conn.cursor()
        
        query = "SELECT s.id, s.name, s.address FROM stores s LEFT JOIN categories c ON s.category_id = c.id WHERE 1=1 "
        params = []
        if search_text:
            query += " AND s.name LIKE ?"
            params.append(f"%{search_text}%")
        if cat_filter and cat_filter != "Tất cả loại":
            query += " AND c.name = ?"
            params.append(cat_filter)
            
        query += " ORDER BY s.name ASC"
        cur.execute(query, params)
        stores = cur.fetchall()
        conn.close()
        
        for store_id, name, address in stores:
            btn_text = f"{name} - {address}" if address else name
            btn = ctk.CTkButton(self.store_list_frame, text=btn_text, fg_color="#333", anchor="w", 
                                command=lambda s_id=store_id: self.on_store_select(s_id))
            btn.pack(fill="x", pady=2, padx=5)

        try:
            self.store_list_frame._parent_canvas.yview_moveto(0)
        except Exception: pass

    def filter_stores(self, event=None):
        self.load_store_list()

    def on_store_select(self, store_id):
        self.current_store_id = store_id
        conn = create_connection()
        cur = conn.cursor()
        cur.execute('''SELECT s.name, c.name, s.tags, s.address, s.phone, s.website, s.latitude, s.longitude 
                       FROM stores s LEFT JOIN categories c ON s.category_id = c.id 
                       WHERE s.id=?''', (store_id,))
        row = cur.fetchone()
        conn.close()
        
        if row:
            self.clear_form(keep_id=True)
            self.entries["name"].insert(0, row[0] or "")
            if row[1]: self.category_combo.set(row[1])
            self.entries["tags"].insert(0, row[2] or "")
            self.entries["address"].insert(0, row[3] or "")
            self.entries["phone"].insert(0, row[4] or "")
            self.entries["website"].insert(0, row[5] or "")
            if row[6] is not None: self.lat_entry.insert(0, str(row[6]))
            if row[7] is not None: self.lng_entry.insert(0, str(row[7]))

    def clear_form(self, keep_id=False):
        if not keep_id: self.current_store_id = None
        for key, entry in self.entries.items():
            if key != "category": entry.delete(0, tk.END)
        self.category_combo.set("")
        self.lat_entry.delete(0, tk.END)
        self.lng_entry.delete(0, tk.END)

    def extract_coordinates(self):
        url = self.entries["gg_maps"].get()
        match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
        if match:
            self.lat_entry.delete(0, tk.END)
            self.lat_entry.insert(0, match.group(1))
            self.lng_entry.delete(0, tk.END)
            self.lng_entry.insert(0, match.group(2))
        else:
            messagebox.showwarning("Lỗi", "Không tìm thấy tọa độ trong link Google Maps.")

    def get_form_data(self):
        cat_name = self.category_combo.get().strip()
        conn = create_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM categories WHERE name=?", (cat_name,))
        row = cur.fetchone()
        if row: cat_id = row[0]
        else:
            cur.execute("INSERT INTO categories (name) VALUES (?)", (cat_name,))
            cat_id = cur.lastrowid
            conn.commit()
        conn.close()
        
        lat = self.lat_entry.get().strip()
        lng = self.lng_entry.get().strip()
        
        return (
            self.entries["name"].get().strip(),
            cat_id,
            self.entries["tags"].get().strip(),
            self.entries["address"].get().strip(),
            self.entries["phone"].get().strip(),
            self.entries["website"].get().strip(),
            float(lat) if lat else None,
            float(lng) if lng else None
        )

    def save_store(self):
        data = self.get_form_data()
        if not data[0]:
            messagebox.showerror("Lỗi", "Tên tiệm không được để trống!")
            return
        conn = create_connection()
        cur = conn.cursor()
        cur.execute('''INSERT INTO stores (name, category_id, tags, address, phone, website, latitude, longitude) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', data)
        conn.commit()
        conn.close()
        messagebox.showinfo("Thành công", "Đã lưu tiệm mới!")
        self.load_categories()
        self.load_store_list()
        self.clear_form()

    def update_store(self):
        if not self.current_store_id:
            messagebox.showerror("Lỗi", "Hãy chọn một tiệm ở danh sách trên để cập nhật!")
            return
        data = self.get_form_data() + (self.current_store_id,)
        conn = create_connection()
        cur = conn.cursor()
        cur.execute('''UPDATE stores SET name=?, category_id=?, tags=?, address=?, phone=?, website=?, latitude=?, longitude=?
                       WHERE id=?''', data)
        conn.commit()
        conn.close()
        messagebox.showinfo("Thành công", "Đã cập nhật tiệm!")
        self.load_categories()
        self.load_store_list()

    def delete_store(self):
        if not self.current_store_id: return
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa tiệm này?"):
            conn = create_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM stores WHERE id=?", (self.current_store_id,))
            conn.commit()
            conn.close()
            self.clear_form()
            self.load_store_list()
            messagebox.showinfo("Thành công", "Đã xóa tiệm!")

    # ----- CATEGORY MANAGER -----
    def open_category_manager(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Quản Lý Danh Mục (Loại Tiệm)")
        dialog.geometry("500x500")
        dialog.transient(self)
        dialog.grab_set()
        
        list_frame = ctk.CTkScrollableFrame(dialog, height=300)
        list_frame.pack(fill="x", padx=20, pady=20)
        
        def reload_cats():
            for w in list_frame.winfo_children(): w.destroy()
            conn = create_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM categories ORDER BY name ASC")
            for cat_id, cat_name in cur.fetchall():
                row_f = ctk.CTkFrame(list_frame, fg_color="transparent")
                row_f.pack(fill="x", pady=2)
                ctk.CTkLabel(row_f, text=cat_name, anchor="w").pack(side="left", padx=5)
                
                btn_del = ctk.CTkButton(row_f, text="Xóa", width=50, fg_color="#b32d2d", hover_color="#8f2424", command=lambda cid=cat_id: delete_cat(cid))
                btn_del.pack(side="right", padx=2)
                btn_edit = ctk.CTkButton(row_f, text="Sửa", width=50, fg_color="#444", command=lambda cid=cat_id, cname=cat_name: edit_cat(cid, cname))
                btn_edit.pack(side="right", padx=2)
            conn.close()
            self.load_categories()
            self.load_store_list()
            
        def delete_cat(cid):
            if messagebox.askyesno("Cảnh báo", "Xóa danh mục này sẽ làm các tiệm đang dùng bị mất loại. Tiếp tục?", parent=dialog):
                conn = create_connection()
                cur = conn.cursor()
                cur.execute("UPDATE stores SET category_id = NULL WHERE category_id = ?", (cid,))
                cur.execute("DELETE FROM categories WHERE id = ?", (cid,))
                conn.commit()
                conn.close()
                reload_cats()
                
        def edit_cat(cid, old_name):
            dialog_ask = ctk.CTkInputDialog(text="Nhập tên mới:", title="Sửa Danh Mục")
            new_name = dialog_ask.get_input()
            if new_name and new_name.strip() != old_name:
                conn = create_connection()
                cur = conn.cursor()
                try:
                    cur.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name.strip(), cid))
                    conn.commit()
                except sqlite3.IntegrityError:
                    messagebox.showerror("Lỗi", "Tên danh mục này đã tồn tại!", parent=dialog)
                conn.close()
                reload_cats()
        
        reload_cats()
        
        add_frame = ctk.CTkFrame(dialog)
        add_frame.pack(fill="x", padx=20, pady=10)
        new_cat_entry = ctk.CTkEntry(add_frame, placeholder_text="Tên loại tiệm mới...")
        new_cat_entry.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        
        def add_cat():
            name = new_cat_entry.get().strip()
            if name:
                conn = create_connection()
                cur = conn.cursor()
                try:
                    cur.execute("INSERT INTO categories (name) VALUES (?)", (name,))
                    conn.commit()
                    new_cat_entry.delete(0, tk.END)
                    reload_cats()
                except sqlite3.IntegrityError:
                    messagebox.showerror("Lỗi", "Danh mục đã tồn tại!", parent=dialog)
                conn.close()
        ctk.CTkButton(add_frame, text="Thêm", width=60, command=add_cat).pack(side="right", padx=5, pady=5)

    # ----- JSON IMPORT DIALOG -----
    def open_json_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Nhập JSON Hàng Loạt")
        dialog.geometry("600x400")
        dialog.transient(self)
        dialog.grab_set()
        
        lbl = ctk.CTkLabel(dialog, text="Dán chuỗi JSON vào bên dưới:")
        lbl.pack(pady=10)
        
        textbox = ctk.CTkTextbox(dialog, width=550, height=250)
        textbox.pack(pady=10)
        textbox.insert("0.0", '[\n  {\n    "name": "Tiệm 1",\n    "category": "nail salon",\n    "tags": "tag1",\n    "address": "Địa chỉ",\n    "phone": "SĐT",\n    "website": "",\n    "latitude": 0.0,\n    "longitude": 0.0\n  }\n]')
        
        def process_json():
            json_str = textbox.get("0.0", tk.END).strip()
            if not json_str: return
            try:
                data = json.loads(json_str)
                if not isinstance(data, list): raise ValueError("Phải là một list các object.")
            except Exception as e:
                messagebox.showerror("Lỗi JSON", f"Định dạng lỗi:\n{e}", parent=dialog)
                return
            conn = create_connection()
            cur = conn.cursor()
            count = 0
            for item in data:
                name = item.get("name")
                if not name: continue
                cat_name = item.get("category", "")
                cat_id = None
                if cat_name:
                    cur.execute("SELECT id FROM categories WHERE name=?", (cat_name,))
                    r = cur.fetchone()
                    if r: cat_id = r[0]
                    else:
                        cur.execute("INSERT INTO categories (name) VALUES (?)", (cat_name,))
                        cat_id = cur.lastrowid
                cur.execute('''INSERT INTO stores (name, category_id, tags, address, phone, website, latitude, longitude)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                            (name, cat_id, item.get("tags",""), item.get("address",""), 
                             item.get("phone",""), item.get("website",""), 
                             item.get("latitude"), item.get("longitude")))
                count += 1
            conn.commit()
            conn.close()
            messagebox.showinfo("Thành công", f"Đã thêm {count} tiệm!", parent=dialog)
            dialog.destroy()
            self.load_categories()
            self.load_store_list()
        ctk.CTkButton(dialog, text="Bắt đầu Import", command=process_json).pack(pady=10)

    # ----- ADMIN & UPDATE -----
    def admin_login(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Đăng nhập Quản Trị")
        dialog.geometry("360x320")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        
        # Center window
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 180
        y = self.winfo_y() + (self.winfo_height() // 2) - 160
        dialog.geometry(f"360x320+{x}+{y}")

        frame = ctk.CTkFrame(dialog, fg_color="#1e1e1e")
        frame.pack(fill="both", expand=True, padx=30, pady=30)
        
        ctk.CTkLabel(frame, text="⚠️ Khu Vực Quản Trị", font=("Arial", 16, "bold")).pack(pady=(15, 20))
        
        ctk.CTkLabel(frame, text="Tài khoản:", anchor="w").pack(fill="x", padx=10)
        user_entry = ctk.CTkEntry(frame, height=40, placeholder_text="Nhập tên tài khoản")
        user_entry.pack(fill="x", padx=10, pady=(4, 12))
        
        ctk.CTkLabel(frame, text="Mật khẩu:", anchor="w").pack(fill="x", padx=10)
        pass_entry = ctk.CTkEntry(frame, height=40, show="*", placeholder_text="Nhập mật khẩu")
        pass_entry.pack(fill="x", padx=10, pady=(4, 20))
        
        def login(event=None):
            if user_entry.get() == "admintd" and pass_entry.get() == "admintd1":
                dialog.destroy()
                self.open_admin_panel()
            else:
                messagebox.showerror("Sai thông tin", "Tài khoản hoặc mật khẩu không đúng!", parent=dialog)
                pass_entry.delete(0, tk.END)
                pass_entry.focus()
                
        ctk.CTkButton(frame, text="Đăng nhập", height=42, fg_color="#006400", hover_color="#008000", command=login).pack(fill="x", padx=10)
        
        # Hỗ trợ bấm Enter để đăng nhập
        dialog.bind("<Return>", login)
        user_entry.focus()

    def open_admin_panel(self):
        panel = ctk.CTkToplevel(self)
        panel.title("Cài Đặt Hệ Thống")
        panel.geometry("500x400")
        panel.transient(self)
        panel.grab_set()
        
        settings = get_settings()
        
        ctk.CTkLabel(panel, text="Tên Ứng Dụng:").grid(row=0, column=0, sticky="w", padx=20, pady=10)
        name_entry = ctk.CTkEntry(panel, width=300)
        name_entry.insert(0, settings.get('app_name', ''))
        name_entry.grid(row=0, column=1, pady=10)
        
        ctk.CTkLabel(panel, text="Phiên Bản (Version):").grid(row=1, column=0, sticky="w", padx=20, pady=10)
        ver_entry = ctk.CTkEntry(panel, width=300)
        ver_entry.insert(0, settings.get('app_version', ''))
        ver_entry.grid(row=1, column=1, pady=10)
        
        ctk.CTkLabel(panel, text="Đường dẫn Logo (.ico):").grid(row=2, column=0, sticky="w", padx=20, pady=10)
        logo_frame = ctk.CTkFrame(panel, fg_color="transparent")
        logo_frame.grid(row=2, column=1, pady=10, sticky="w")
        logo_entry = ctk.CTkEntry(logo_frame, width=220)
        logo_entry.insert(0, settings.get('app_logo', ''))
        logo_entry.pack(side="left")
        
        def browse_logo():
            path = filedialog.askopenfilename(filetypes=[("Icon files", "*.ico")])
            if path:
                logo_entry.delete(0, tk.END)
                logo_entry.insert(0, path)
        ctk.CTkButton(logo_frame, text="Chọn", width=60, command=browse_logo).pack(side="left", padx=5)
        
        ctk.CTkLabel(panel, text="GitHub Repo (Auto-Update):\n(Ví dụ: username/repo)").grid(row=3, column=0, sticky="w", padx=20, pady=10)
        repo_entry = ctk.CTkEntry(panel, width=300)
        repo_entry.insert(0, settings.get('github_repo', ''))
        repo_entry.grid(row=3, column=1, pady=10)
        
        def save():
            new_name = name_entry.get().strip()
            new_ver = ver_entry.get().strip()
            new_logo = logo_entry.get().strip()
            new_repo = repo_entry.get().strip()
            
            set_setting('app_name', new_name)
            set_setting('app_version', new_ver)
            set_setting('app_logo', new_logo)
            set_setting('github_repo', new_repo)
            
            # Áp dụng ngay tiêu đề cửa sổ
            self.title(f"{new_name} v{new_ver}")
            
            # Áp dụng ngay icon nếu file hợp lệ
            if new_logo and os.path.exists(new_logo) and new_logo.lower().endswith('.ico'):
                try:
                    self.iconbitmap(new_logo)
                    messagebox.showinfo("Thành công", "Dã lưu và áp dụng cài đặt thành công!", parent=panel)
                except Exception as e:
                    messagebox.showwarning("Cảnh báo", f"Đã lưu, nhưng không đổi được icon: {e}", parent=panel)
            else:
                if new_logo:
                    messagebox.showwarning("Cảnh báo", "Đã lưu! Nhưng logo phải là file .ico hợp lệ mới hiển thị được.", parent=panel)
                else:
                    messagebox.showinfo("Thành công", "Đã lưu cài đặt thành công!", parent=panel)
            panel.destroy()
            
        ctk.CTkButton(panel, text="Lưu Cấu Hình", fg_color="#006400", hover_color="#008000", command=save).grid(row=4, column=0, columnspan=2, pady=30)

    def check_for_updates(self):
        settings = get_settings()
        repo = settings.get('github_repo', '').strip()
        current_version = settings.get('app_version', '1.0.0').strip()
        if not repo: return
        
        def worker():
            try:
                url = f"https://api.github.com/repos/{repo}/releases/latest"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                with urllib.request.urlopen(req, context=ctx) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    tag_name = data.get('tag_name', '').strip()
                    assets = data.get('assets', [])
                    
                    if tag_name and tag_name != current_version and tag_name.replace('v', '') != current_version.replace('v', ''):
                        exe_url = None
                        for asset in assets:
                            if asset['name'].endswith('.exe'):
                                exe_url = asset['browser_download_url']
                                break
                                
                        if exe_url:
                            self.after(0, lambda: self.prompt_update(tag_name, exe_url))
            except Exception as e:
                print("Check update error:", e)
                
        threading.Thread(target=worker, daemon=True).start()

    def prompt_update(self, new_version, download_url):
        if messagebox.askyesno("Cập nhật phần mềm", f"Phát hiện phiên bản mới {new_version}.\nBạn có muốn tự động tải và cập nhật ngay không?"):
            self.perform_update(download_url)

    def perform_update(self, download_url):
        update_win = ctk.CTkToplevel(self)
        update_win.title("Đang cập nhật...")
        update_win.geometry("300x150")
        update_win.transient(self)
        update_win.grab_set()
        
        lbl = ctk.CTkLabel(update_win, text="Đang tải dữ liệu. Vui lòng không tắt máy...")
        lbl.pack(pady=20)
        progress = ctk.CTkProgressBar(update_win)
        progress.pack(pady=10, padx=20, fill="x")
        progress.set(0)
        
        def worker():
            try:
                # Tải file .exe
                temp_exe = "update_temp.exe"
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                req = urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, context=ctx) as response:
                    total_size = int(response.info().get('Content-Length').strip())
                    downloaded = 0
                    chunk_size = 8192
                    with open(temp_exe, 'wb') as f:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk: break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                p = downloaded / total_size
                                self.after(0, lambda p=p: progress.set(p))
                
                # Tạo file bat để thay thế exe hiện tại
                current_exe = sys.argv[0] if sys.argv[0].endswith('.exe') else sys.executable
                current_exe_name = os.path.basename(current_exe)
                
                bat_content = f"""@echo off
timeout /t 2 /nobreak >nul
del "{current_exe_name}"
rename "update_temp.exe" "{current_exe_name}"
start "" "{current_exe_name}"
del "%~f0"
"""
                with open("updater.bat", "w") as f:
                    f.write(bat_content)
                
                self.after(0, lambda: self.finish_update())
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("Lỗi Cập nhật", str(e), parent=update_win))
                self.after(0, update_win.destroy)
                
        threading.Thread(target=worker, daemon=True).start()
        
    def finish_update(self):
        messagebox.showinfo("Hoàn tất", "Tải xong! Phần mềm sẽ tự động khởi động lại.")
        subprocess.Popen("updater.bat", shell=True)
        self.destroy()
        sys.exit()

if __name__ == "__main__":
    app = App()
    app.mainloop()
