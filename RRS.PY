import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import importlib
import os
import sqlite3
import hashlib
import csv
try:
    qrcode = importlib.import_module("qrcode")
except ImportError:
    qrcode = None
try:
    Image = importlib.import_module("PIL.Image")
    ImageTk = importlib.import_module("PIL.ImageTk")
    ImageOps = importlib.import_module("PIL.ImageOps")
except ImportError:
    Image = None
    ImageTk = None
try:
    docx = importlib.import_module("docx")
except ImportError:
    docx = None
import random

# ==========================================
# DATA
# ==========================================
reservations = []
packages = {
    "Birthday": {"Basic": 3000, "Premium": 5000, "Deluxe": 8000},
    "Wedding": {"Basic": 15000, "Premium": 25000, "Deluxe": 40000},
    "Anniversary": {"Basic": 5000, "Premium": 8000, "Deluxe": 12000},
    "Graduation": {"Basic": 4000, "Premium": 7000, "Deluxe": 10000}
}

DISCOUNT_CODE = "SAVE20"
DISCOUNT_PERCENT = 20

# ==========================================
# DATABASE (SQLite) - reservations persist between runs
# ==========================================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reservations.db")
db_conn = sqlite3.connect(DB_PATH)
db_cursor = db_conn.cursor()
db_cursor.execute("""
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact TEXT NOT NULL,
    occasion TEXT NOT NULL,
    package TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    guests INTEGER NOT NULL,
    price REAL NOT NULL,
    discounted INTEGER NOT NULL DEFAULT 0
)
""")
db_conn.commit()

db_cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
)
""")
db_conn.commit()


def hash_password(plain_text_password):
    return hashlib.sha256(plain_text_password.encode("utf-8")).hexdigest()


# Seed a default admin account on first run only, so the app works
# out of the box. Change the password from inside the app afterward
# (or directly in the database) rather than editing this seed value.
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"

db_cursor.execute("SELECT COUNT(*) FROM admins")
if db_cursor.fetchone()[0] == 0:
    db_cursor.execute(
        "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
        (DEFAULT_ADMIN_USERNAME, hash_password(DEFAULT_ADMIN_PASSWORD))
    )
    db_conn.commit()

# Drop a file named "logo.png" next to this script to use your own picture
# in the heading frame. If it isn't found (or Pillow isn't installed), a
# generated calendar icon is drawn instead, so the header always looks complete.
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")

# Shared color palette (used by both the login screen and the main app)
COLOR_DARK = "#101828"
COLOR_ACCENT = "#2878F0"
COLOR_ACCENT_HOVER = "#1E5FC7"
COLOR_BG = "#F4F6F8"
COLOR_DANGER = "#D64545"
COLOR_DANGER_HOVER = "#B93A3A"
COLOR_SUCCESS = "#00C853"
COLOR_MUTED = "#687386"


# ==========================================
# SMALL UI HELPERS (hover effects)
# ==========================================
def _tint(hex_color, amount):
    """Lighten a hex color toward white. amount=0 -> unchanged, amount=1 -> white."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return "#FFFFFF"
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02X}{g:02X}{b:02X}"


def add_hover(widget, normal_bg, hover_bg):
    """Give any tk.Button a smooth color change on mouse hover."""
    def on_enter(_e):
        widget.config(bg=hover_bg)

    def on_leave(_e):
        widget.config(bg=normal_bg)

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


def draw_calendar_icon(canvas, cx, cy, size=64):
    """Draws a simple flat-style calendar/event icon centered at (cx, cy)."""
    half = size // 2
    top = cy - half
    bottom = cy + half
    left = cx - half
    right = cx + half

    canvas.create_rectangle(left, top + 10, right, bottom, fill="white", outline="#101828", width=2)
    canvas.create_rectangle(left, top + 10, right, top + 26, fill=COLOR_ACCENT, outline=COLOR_ACCENT)
    canvas.create_rectangle(left + 10, top, left + 16, top + 16, fill="#101828", outline="")
    canvas.create_rectangle(right - 16, top, right - 10, top + 16, fill="#101828", outline="")
    grid_left = left + 8
    grid_top = top + 34
    cell_w, cell_h, gap = 12, 9, 4
    for row in range(2):
        for col in range(3):
            x0 = grid_left + col * (cell_w + gap)
            y0 = grid_top + row * (cell_h + gap)
            fill = COLOR_DANGER if (row, col) == (0, 1) else "#D1D5DB"
            canvas.create_rectangle(x0, y0, x0 + cell_w, y0 + cell_h, fill=fill, outline="")


def build_logo_widget(parent, box_bg="white"):
    """
    Returns a small 'picture frame' style widget:
    - shows logo.png (next to this script) if it exists and Pillow is available
    - otherwise falls back to a drawn calendar/event icon, so the frame is
      never empty.
    """
    frame = tk.Frame(parent, bg=box_bg, highlightbackground=COLOR_ACCENT, highlightthickness=2)
    inner = tk.Frame(frame, bg=box_bg)
    inner.pack(padx=6, pady=6)

    if Image is not None and ImageTk is not None and os.path.exists(LOGO_PATH):
        try:
            img = Image.open(LOGO_PATH).convert("RGB").resize((72, 72))
            photo = ImageTk.PhotoImage(img)
            logo_label = tk.Label(inner, image=photo, bg=box_bg)
            logo_label.image = photo  # keep a reference so it isn't garbage-collected
            logo_label.pack()
            return frame
        except Exception:
            pass  # any load problem -> fall back to the drawn icon below

    canvas = tk.Canvas(inner, width=72, height=72, bg=box_bg, highlightthickness=0)
    canvas.pack()
    draw_calendar_icon(canvas, 36, 36, size=60)
    return frame


# ==========================================
# LOGIN SCREEN
# ==========================================
def show_login_screen():
    login = tk.Tk()
    login.title("Event Manager Pro - Admin Login")
    login.geometry("900x520")
    login.resizable(False, False)
    login.configure(bg=COLOR_BG)

    # Center the window on screen
    login.update_idletasks()
    w, h = 900, 520
    x = (login.winfo_screenwidth() // 2) - (w // 2)
    y = (login.winfo_screenheight() // 2) - (h // 2)
    login.geometry(f"{w}x{h}+{x}+{y}")

    # --- Left branding panel (dark) ---
    left_panel = tk.Frame(login, bg=COLOR_DARK, width=380)
    left_panel.pack(side="left", fill="y")
    left_panel.pack_propagate(False)

    branding_wrap = tk.Frame(left_panel, bg=COLOR_DARK)
    branding_wrap.place(relx=0.5, rely=0.5, anchor="center")

    logo_widget = build_logo_widget(branding_wrap, box_bg=COLOR_DARK)
    logo_widget.pack(pady=(0, 20))

    tk.Label(
        branding_wrap, text="EVENT\nMANAGER", font=("Segoe UI", 26, "bold"),
        fg="white", bg=COLOR_DARK, justify="center"
    ).pack()
    tk.Label(
        branding_wrap, text="PRO EDITION • 2026", font=("Segoe UI", 10, "bold"),
        fg=COLOR_ACCENT, bg=COLOR_DARK
    ).pack(pady=(4, 0))
    tk.Frame(branding_wrap, bg=COLOR_ACCENT, width=50, height=3).pack(pady=16)
    tk.Label(
        branding_wrap,
        text="Reservation • Catering\nEvent Planning System",
        font=("Segoe UI", 9), fg="#9AA5B8", bg=COLOR_DARK, justify="center"
    ).pack()

    # --- Right login form panel (white) ---
    right_panel = tk.Frame(login, bg="white")
    right_panel.pack(side="right", fill="both", expand=True)

    form_wrap = tk.Frame(right_panel, bg="white")
    form_wrap.place(relx=0.5, rely=0.5, anchor="center")

    tk.Label(
        form_wrap, text="Admin Login", font=("Segoe UI", 22, "bold"),
        fg=COLOR_DARK, bg="white"
    ).grid(row=0, column=0, sticky="w", pady=(0, 4))
    tk.Label(
        form_wrap, text="Sign in to manage reservations and settings.",
        font=("Segoe UI", 10), fg=COLOR_MUTED, bg="white"
    ).grid(row=1, column=0, sticky="w", pady=(0, 25))

    tk.Label(
        form_wrap, text="USERNAME", font=("Segoe UI", 8, "bold"),
        fg=COLOR_MUTED, bg="white"
    ).grid(row=2, column=0, sticky="w")
    username_entry = tk.Entry(
        form_wrap, font=("Segoe UI", 12), width=28, bd=0,
        relief="flat", highlightthickness=1,
        highlightbackground="#D9DEE7", highlightcolor=COLOR_ACCENT
    )
    username_entry.grid(row=3, column=0, sticky="ew", pady=(4, 16), ipady=8)
    username_entry.focus()

    tk.Label(
        form_wrap, text="PASSWORD", font=("Segoe UI", 8, "bold"),
        fg=COLOR_MUTED, bg="white"
    ).grid(row=4, column=0, sticky="w")
    password_entry = tk.Entry(
        form_wrap, font=("Segoe UI", 12), width=28, bd=0,
        relief="flat", show="•", highlightthickness=1,
        highlightbackground="#D9DEE7", highlightcolor=COLOR_ACCENT
    )
    password_entry.grid(row=5, column=0, sticky="ew", pady=(4, 8), ipady=8)

    remembered_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".remembered_user.txt")
    if os.path.exists(remembered_file):
        try:
            with open(remembered_file, "r") as f:
                saved_username = f.read().strip()
            if saved_username:
                username_entry.delete(0, tk.END)
                username_entry.insert(0, saved_username)
                password_entry.focus()
        except Exception:
            pass

    show_pw_var = tk.BooleanVar()
    remember_var = tk.BooleanVar(value=os.path.exists(remembered_file))

    def toggle_password():
        password_entry.config(show="" if show_pw_var.get() else "•")

    checks_row = tk.Frame(form_wrap, bg="white")
    checks_row.grid(row=6, column=0, sticky="w", pady=(0, 8))

    tk.Checkbutton(
        checks_row, text="Show password", variable=show_pw_var, command=toggle_password,
        font=("Segoe UI", 8), bg="white", fg=COLOR_MUTED,
        activebackground="white", bd=0
    ).pack(side="left")

    tk.Checkbutton(
        checks_row, text="Remember me", variable=remember_var,
        font=("Segoe UI", 8), bg="white", fg=COLOR_MUTED,
        activebackground="white", bd=0
    ).pack(side="left", padx=(15, 0))

    error_label = tk.Label(form_wrap, text="", font=("Segoe UI", 9, "bold"), fg=COLOR_DANGER, bg="white")
    error_label.grid(row=7, column=0, sticky="w")

    def attempt_login(event=None):
        username = username_entry.get().strip()
        password = password_entry.get().strip()

        db_cursor.execute("SELECT password_hash FROM admins WHERE username = ?", (username,))
        result = db_cursor.fetchone()
        login_ok = result is not None and result[0] == hash_password(password)

        if login_ok:
            try:
                if remember_var.get():
                    with open(remembered_file, "w") as f:
                        f.write(username)
                elif os.path.exists(remembered_file):
                    os.remove(remembered_file)
            except Exception:
                pass
            login.destroy()
            launch_main_app()
        else:
            error_label.config(text="Invalid username or password. Please try again.")
            password_entry.delete(0, tk.END)

    login_btn = tk.Button(
        form_wrap, text="LOGIN", bg=COLOR_ACCENT, fg="white",
        font=("Segoe UI", 11, "bold"), relief="flat", bd=0,
        height=2, width=28, command=attempt_login, cursor="hand2"
    )
    login_btn.grid(row=8, column=0, sticky="ew", pady=(15, 0))
    add_hover(login_btn, COLOR_ACCENT, COLOR_ACCENT_HOVER)

    login.bind("<Return>", attempt_login)

    tk.Label(
        form_wrap, text="Default demo credentials: admin / admin123",
        font=("Segoe UI", 8), fg="#B7BFCC", bg="white"
    ).grid(row=9, column=0, sticky="w", pady=(18, 0))

    login.mainloop()


# ==========================================
# MAIN APP
# ==========================================
def launch_main_app():
    # ------------------------------------------
    # FUNCTIONS
    # ------------------------------------------
    def update_packages(event=None):
        occasion = occasion_combo.get()
        if occasion:
            package_combo["values"] = list(packages[occasion].keys())
            package_combo.current(0)
            update_price_preview()

    def update_price_preview(event=None):
        try:
            occasion = occasion_combo.get()
            package = package_combo.get()
            if occasion and package:
                price = packages[occasion][package]
                code = discount_entry.get().strip().upper()
                if code == DISCOUNT_CODE:
                    discount = price * (DISCOUNT_PERCENT / 100)
                    final_price = price - discount
                    price_label.config(text=f"₱{final_price:,.0f} (was ₱{price:,}) -{DISCOUNT_PERCENT}% OFF!", fg=COLOR_SUCCESS)
                else:
                    price_label.config(text=f"₱{price:,}", fg=COLOR_ACCENT)
        except Exception:
            pass

    def clear_fields():
        for e in [name_entry, contact_entry, date_entry, time_entry, guests_entry, discount_entry]:
            e.delete(0, tk.END)
        occasion_combo.set("")
        package_combo.set("")
        price_label.config(text="₱0", fg=COLOR_ACCENT)

    def load_reservations_from_db():
        global reservations
        db_cursor.execute(
            "SELECT id, name, contact, occasion, package, date, time, guests, price, discounted "
            "FROM reservations ORDER BY id"
        )
        rows = db_cursor.fetchall()
        reservations = [
            {
                "id": row[0], "name": row[1], "contact": row[2], "occasion": row[3],
                "package": row[4], "date": row[5], "time": row[6], "guests": row[7],
                "price": row[8], "discounted": bool(row[9])
            }
            for row in rows
        ]

    def make_reservation():
        name = name_entry.get().strip()
        contact = contact_entry.get().strip()
        occasion = occasion_combo.get()
        package = package_combo.get()
        date = date_entry.get().strip()
        time = time_entry.get().strip()
        guests = guests_entry.get().strip()
        discount_code = discount_entry.get().strip().upper()

        if not all([name, contact, occasion, package, date, time, guests]):
            messagebox.showwarning("Missing Information", "Please complete all required fields.")
            return
        try:
            guests = int(guests)
            if guests <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Number", "Guests must be > 0")
            return

        price = packages[occasion][package]
        is_discounted = False
        if discount_code == DISCOUNT_CODE:
            price = price * (1 - DISCOUNT_PERCENT / 100)
            is_discounted = True
        elif discount_code != "":
            messagebox.showerror("Invalid Code", f"Code '{discount_code}' is invalid. Use {DISCOUNT_CODE}")
            return

        db_cursor.execute(
            "INSERT INTO reservations (name, contact, occasion, package, date, time, guests, price, discounted) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, contact, occasion, package, date, time, guests, price, int(is_discounted))
        )
        db_conn.commit()

        load_reservations_from_db()
        update_table()
        update_dashboard()
        clear_fields()
        messagebox.showinfo("Success", f"Reservation Successful!\n{occasion} - {package}\nTotal: ₱{price:,.0f} {'(with 20% OFF)' if is_discounted else ''}")

    def update_table():
        for item in reservation_table.get_children():
            reservation_table.delete(item)
        for r in reservations:
            tag = "discount" if r.get("discounted") else ""
            reservation_table.insert("", tk.END, values=(r["id"], r["name"], r["contact"], r["occasion"], r["package"], r["date"], r["time"], r["guests"], f"₱{r['price']:,.0f}"), tags=(tag,))
        reservation_table.tag_configure("discount", background="#E8F5E9", foreground="#2E7D32")

    def cancel_reservation():
        selected = reservation_table.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Select a reservation first.")
            return
        values = reservation_table.item(selected[0], "values")
        reservation_id = int(values[0])
        if messagebox.askyesno("Cancel", f"Cancel reservation for {values[1]}?"):
            db_cursor.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
            db_conn.commit()
            load_reservations_from_db()
            update_table()
            update_dashboard()

    # ------------------- Receipt (Word doc / text) -------------------
    def _write_receipt_docx(r, file_path):
        document = docx.Document()
        document.add_heading("EVENT MANAGER PRO", level=1)
        document.add_paragraph("Official Reservation Receipt")

        table = document.add_table(rows=0, cols=2)
        table.style = "Light Grid Accent 1"
        rows = [
            ("Receipt No.", str(r["id"])),
            ("Customer Name", r["name"]),
            ("Contact Number", r["contact"]),
            ("Occasion", r["occasion"]),
            ("Package", r["package"]),
            ("Date", r["date"]),
            ("Time", r["time"]),
            ("Guests", str(r["guests"])),
            ("Discount Applied", f"Yes ({DISCOUNT_PERCENT}% OFF)" if r["discounted"] else "No"),
            ("Total Price", f"P{r['price']:,.2f}"),
        ]
        for label, value in rows:
            cells = table.add_row().cells
            cells[0].text = label
            cells[1].text = value

        document.add_paragraph("")
        document.add_paragraph("Thank you for booking with Event Manager Pro!")
        document.save(file_path)

    def _write_receipt_txt(r, file_path):
        lines = [
            "==========================================",
            "        EVENT MANAGER PRO - RECEIPT",
            "==========================================",
            f"Receipt No.:      {r['id']}",
            f"Customer Name:    {r['name']}",
            f"Contact Number:   {r['contact']}",
            f"Occasion:         {r['occasion']}",
            f"Package:          {r['package']}",
            f"Date:             {r['date']}",
            f"Time:             {r['time']}",
            f"Guests:           {r['guests']}",
            f"Discount Applied: {'Yes (' + str(DISCOUNT_PERCENT) + '% OFF)' if r['discounted'] else 'No'}",
            f"Total Price:      P{r['price']:,.2f}",
            "==========================================",
            "  Thank you for booking with Event Manager Pro!",
            "==========================================",
        ]
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def print_receipt():
        selected = reservation_table.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Select a reservation to generate a receipt for.")
            return

        values = reservation_table.item(selected[0], "values")
        reservation_id = int(values[0])
        r = next((res for res in reservations if res["id"] == reservation_id), None)
        if r is None:
            messagebox.showerror("Error", "Reservation not found.")
            return

        safe_name = r["name"].replace(" ", "_")
        if docx is not None:
            file_path = filedialog.asksaveasfilename(
                title="Save Receipt",
                initialfile=f"Receipt_{safe_name}_{r['id']}",
                defaultextension=".docx",
                filetypes=[("Word Document", "*.docx"), ("Text File", "*.txt")]
            )
        else:
            file_path = filedialog.asksaveasfilename(
                title="Save Receipt (install python-docx for Word format)",
                initialfile=f"Receipt_{safe_name}_{r['id']}",
                defaultextension=".txt",
                filetypes=[("Text File", "*.txt")]
            )

        if not file_path:
            return

        try:
            if file_path.lower().endswith(".docx") and docx is not None:
                _write_receipt_docx(r, file_path)
            else:
                _write_receipt_txt(r, file_path)
            messagebox.showinfo("Receipt Saved", f"Receipt saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save receipt:\n{e}")

    # ------------------- Export full list to spreadsheet (CSV) -------------------
    def export_to_spreadsheet():
        if not reservations:
            messagebox.showwarning("No Data", "There are no reservations to export yet.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Export Reservations to Spreadsheet",
            initialfile="reservations_export",
            defaultextension=".csv",
            filetypes=[("CSV Spreadsheet (opens in Excel)", "*.csv")]
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["No.", "Name", "Contact", "Occasion", "Package", "Date", "Time", "Guests", "Discounted", "Total Price"])
                for r in reservations:
                    writer.writerow([
                        r["id"], r["name"], r["contact"], r["occasion"], r["package"],
                        r["date"], r["time"], r["guests"],
                        "Yes" if r["discounted"] else "No", f"{r['price']:.2f}"
                    ])
            messagebox.showinfo("Export Complete", f"Reservations exported to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export reservations:\n{e}")

    def update_dashboard():
        total_rev = sum(r["price"] for r in reservations)
        total_guests = sum(r["guests"] for r in reservations)
        count_label.config(text=str(len(reservations)))
        revenue_label.config(text=f"₱{total_rev:,.0f}")
        guests_count_label.config(text=str(total_guests))
        update_chart()

    def update_chart():
        chart_canvas.delete("all")
        canvas_w = int(chart_canvas["width"])
        canvas_h = int(chart_canvas["height"])

        occasion_names = list(packages.keys())
        counts = {name: 0 for name in occasion_names}
        for r in reservations:
            if r["occasion"] in counts:
                counts[r["occasion"]] += 1

        total_bookings = sum(counts.values())
        max_count = max(counts.values()) if counts.values() else 0
        max_count = max(max_count, 1)  # avoid divide-by-zero when everything is 0

        bar_colors = ["#2878F0", "#D64545", "#00A86B", "#9B59B6", "#F5A623"]
        padding_left = 40
        padding_bottom = 34
        padding_top = 15
        chart_area_h = canvas_h - padding_bottom - padding_top
        chart_area_w = canvas_w - padding_left - 20

        # Soft horizontal gridlines for a cleaner, more polished feel
        grid_lines = 4
        for g in range(grid_lines + 1):
            gy = padding_top + (chart_area_h / grid_lines) * g
            chart_canvas.create_line(
                padding_left, gy, canvas_w - 10, gy,
                fill="#F0F2F5", width=1
            )

        if total_bookings == 0:
            chart_canvas.create_text(
                canvas_w / 2, canvas_h / 2 - 5,
                text="No bookings yet — your first reservation will show up here.",
                font=("Segoe UI", 10), fill=COLOR_MUTED
            )

        n = len(occasion_names)
        slot_w = chart_area_w / n if n else 0
        bar_w = min(slot_w * 0.5, 60)

        # baseline (drawn on top of gridlines so it reads clearly)
        chart_canvas.create_line(
            padding_left, canvas_h - padding_bottom,
            canvas_w - 10, canvas_h - padding_bottom,
            fill="#D9DEE7", width=1
        )

        for i, name in enumerate(occasion_names):
            count = counts[name]
            bar_h = (count / max_count) * chart_area_h if max_count else 0
            x_center = padding_left + slot_w * i + slot_w / 2
            x0 = x_center - bar_w / 2
            x1 = x_center + bar_w / 2
            y1 = canvas_h - padding_bottom
            y0 = y1 - bar_h

            color = bar_colors[i % len(bar_colors)]

            if bar_h > 0:
                radius = min(bar_w / 2, 8)
                # rounded-top bar: a rectangle with a rounded cap drawn via an oval + rect overlap
                chart_canvas.create_rectangle(x0, y0 + radius, x1, y1, fill=color, outline="")
                chart_canvas.create_oval(x0, y0, x1, y0 + radius * 2, fill=color, outline="")

            # subtle backdrop column so empty bars still show their "track"
            chart_canvas.create_rectangle(
                x0, padding_top, x1, y1, fill="", outline=""
            )

            # count label above the bar
            if count > 0:
                chart_canvas.create_text(
                    x_center, y0 - 12, text=str(count),
                    font=("Segoe UI", 10, "bold"), fill=COLOR_DARK
                )

            # occasion label below the bar, with a small color swatch beside it
            swatch_y = canvas_h - padding_bottom + 18
            chart_canvas.create_oval(
                x_center - 32, swatch_y - 4, x_center - 24, swatch_y + 4,
                fill=color, outline=""
            )
            chart_canvas.create_text(
                x_center + 6, swatch_y, text=name,
                font=("Segoe UI", 8, "bold"), fill=COLOR_MUTED, anchor="w"
            )

    def generate_qr():
        qr_data = f"EVENT MANAGER DISCOUNT\nCode: {DISCOUNT_CODE}\nGet {DISCOUNT_PERCENT}% OFF on any package!\nScan to claim at counter."
        if qrcode is None:
            img = Image.new("RGB", (150, 150), "white")
        else:
            qr = qrcode.QRCode(version=1, box_size=6, border=2)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color=COLOR_DARK, back_color="white").resize((150, 150))
        return ImageTk.PhotoImage(img)

    def add_placeholder(entry, text):
        entry.insert(0, text)
        entry.config(fg="#98A2B3")

        def focus_in(event):
            if entry.get() == text:
                entry.delete(0, tk.END)
                entry.config(fg="#101828")

        def focus_out(event):
            if entry.get().strip() == "":
                entry.insert(0, text)
                entry.config(fg="#98A2B3")

        entry.bind("<FocusIn>", focus_in)
        entry.bind("<FocusOut>", focus_out)

    # ------------------------------------------
    # MAIN WINDOW
    # ------------------------------------------
    window = tk.Tk()
    window.title("Event Manager Pro - with QR Discount")
    window.geometry("1720x900")
    window.minsize(1300, 750)
    window.configure(bg=COLOR_BG)

    # --- SIDEBAR ---
    sidebar = tk.Frame(window, bg=COLOR_DARK, width=260)
    sidebar.pack(side="left", fill="y")

    header_block = tk.Frame(sidebar, bg=COLOR_DARK)
    header_block.pack(pady=(35, 15), padx=20, fill="x")

    logo_widget = build_logo_widget(header_block, box_bg=COLOR_DARK)
    logo_widget.pack(anchor="w")

    tk.Label(header_block, text="EVENT\nMANAGER", font=("Segoe UI", 22, "bold"), fg="white", bg=COLOR_DARK, justify="left").pack(anchor="w", pady=(10, 2))
    tk.Label(header_block, text="PRO EDITION • 2026", font=("Segoe UI", 9, "bold"), fg=COLOR_ACCENT, bg=COLOR_DARK).pack(anchor="w")

    dash_frame = tk.Frame(sidebar, bg=COLOR_DARK)
    dash_frame.pack(pady=20, padx=15, fill="x")

    # QR CODE AREA
    qr_container = tk.Frame(sidebar, bg="white", highlightbackground="#E0E0E0", highlightthickness=1)
    qr_container.pack(pady=20, padx=15, fill="x")

    tk.Label(qr_container, text="SCAN FOR DISCOUNT", font=("Segoe UI", 9, "bold"), bg="white", fg=COLOR_DANGER).pack(pady=(12, 2))
    qr_photo = generate_qr()
    qr_label = tk.Label(qr_container, image=qr_photo, bg="white")
    qr_label.image = qr_photo
    qr_label.pack(pady=5)

    tk.Label(qr_container, text=f"Code: {DISCOUNT_CODE}", font=("Consolas", 12, "bold"), bg="white", fg=COLOR_DARK).pack()
    tk.Label(qr_container, text=f"Get {DISCOUNT_PERCENT}% OFF\non any package!", font=("Segoe UI", 8), bg="white", fg=COLOR_MUTED, justify="center").pack(pady=(2, 12))

    def logout():
        if messagebox.askyesno("Logout", "Are you sure you want to log out?"):
            window.destroy()
            show_login_screen()

    logout_btn = tk.Button(sidebar, text="Logout", bg="#22304A", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", command=logout, height=2, cursor="hand2")
    logout_btn.pack(side="bottom", fill="x", padx=15, pady=(0, 10))
    add_hover(logout_btn, "#22304A", "#2E3F5E")

    exit_btn = tk.Button(sidebar, text="Exit System", bg=COLOR_DANGER, fg="white", font=("Segoe UI", 10, "bold"), relief="flat", command=window.destroy, height=2, cursor="hand2")
    exit_btn.pack(side="bottom", fill="x", padx=15, pady=(25, 0))
    add_hover(exit_btn, COLOR_DANGER, COLOR_DANGER_HOVER)

    # --- MAIN CONTENT (scrollable, so nothing ever gets clipped) ---
    main_container = tk.Frame(window, bg=COLOR_BG)
    main_container.pack(side="right", fill="both", expand=True)

    main_canvas_scroll = tk.Canvas(main_container, bg=COLOR_BG, highlightthickness=0)
    main_scrollbar = tk.Scrollbar(main_container, orient="vertical", command=main_canvas_scroll.yview)
    main_canvas_scroll.configure(yscrollcommand=main_scrollbar.set)

    main_scrollbar.pack(side="right", fill="y")
    main_canvas_scroll.pack(side="left", fill="both", expand=True)

    main_frame = tk.Frame(main_canvas_scroll, bg=COLOR_BG)
    main_frame_window = main_canvas_scroll.create_window((0, 0), window=main_frame, anchor="nw")

    def _on_main_frame_configure(_event=None):
        main_canvas_scroll.configure(scrollregion=main_canvas_scroll.bbox("all"))

    def _on_canvas_resize(event):
        main_canvas_scroll.itemconfig(main_frame_window, width=event.width)

    main_frame.bind("<Configure>", _on_main_frame_configure)
    main_canvas_scroll.bind("<Configure>", _on_canvas_resize)

    def _on_mousewheel(event):
        main_canvas_scroll.yview_scroll(int(-1 * (event.delta / 120)), "units")

    main_canvas_scroll.bind_all("<MouseWheel>", _on_mousewheel)

    # --- PROMOTION HEADER ---
    header = tk.Frame(main_frame, bg=COLOR_BG)
    header.pack(fill="x", padx=30, pady=(20, 10))

    title_frame = tk.Frame(header, bg=COLOR_BG)
    title_frame.pack(fill="x", pady=(0, 10))

    tk.Label(title_frame, text="EVENT MANAGER", font=("Segoe UI", 20, "bold"), fg=COLOR_DARK, bg=COLOR_BG).pack(side="left")
    tk.Label(title_frame, text="  |  RESERVATION • CATERING • EVENT PLANNING", font=("Segoe UI", 9, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG).pack(side="left", pady=(5, 0))

    # PROMOTIONAL IMAGE
    promo_container = tk.Frame(header, bg="white", highlightbackground="#D9DEE7", highlightthickness=1)
    promo_container.pack(fill="x", expand=True)

    promo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "event_promo.png")

    if Image is not None and ImageTk is not None and os.path.exists(promo_path):
        try:
            promo_img = Image.open(promo_path).convert("RGB")
            promo_img = promo_img.resize((1470, 240), Image.LANCZOS)
            promo_photo = ImageTk.PhotoImage(promo_img)
            promo_label = tk.Label(promo_container, image=promo_photo, bg="white", bd=0, highlightthickness=0)
            promo_label.image = promo_photo
            promo_label.pack(fill="x", expand=True, padx=0, pady=0)
        except Exception as e:
            print("Promotion image error:", e)
            tk.Label(
                promo_container,
                text="EVENT MANAGER\nWedding • Anniversary • Graduation • Catering",
                font=("Segoe UI", 20, "bold"), fg=COLOR_DARK, bg="white", pady=30
            ).pack(fill="x")
    else:
        tk.Label(promo_container, text="EVENT MANAGER", font=("Segoe UI", 24, "bold"), fg=COLOR_DARK, bg="white").pack(pady=(20, 5))
        tk.Label(promo_container, text="Wedding • Anniversary • Graduation • Catering", font=("Segoe UI", 11, "bold"), fg=COLOR_ACCENT, bg="white").pack(pady=(0, 20))

    tk.Label(header, text="Create and manage reservations with exclusive promotional offers.", font=("Segoe UI", 10), fg=COLOR_MUTED, bg=COLOR_BG).pack(anchor="w", pady=(8, 0))

    # DASHBOARD STATS
    stats_frame = tk.Frame(main_frame, bg=COLOR_BG)
    stats_frame.pack(fill="x", padx=30, pady=(10, 6))

    def stat_card(parent, title, value_text, icon_char, accent_color):
        card = tk.Frame(parent, bg="white", highlightbackground="#E5E7EB", highlightthickness=1)
        card.pack(side="left", fill="x", expand=True, padx=(0, 15))

        # Colored accent strip along the top edge
        tk.Frame(card, bg=accent_color, height=4).pack(fill="x", side="top")

        content_row = tk.Frame(card, bg="white")
        content_row.pack(fill="x", padx=15, pady=(14, 14))

        # Icon badge (tinted circle with an icon/glyph centered inside)
        badge = tk.Canvas(content_row, width=46, height=46, bg="white", highlightthickness=0)
        badge.pack(side="left", padx=(0, 14))
        badge.create_oval(2, 2, 44, 44, outline="", fill=_tint(accent_color, 0.85))
        badge.create_text(23, 23, text=icon_char, font=("Segoe UI Emoji", 18), fill=accent_color)

        text_col = tk.Frame(content_row, bg="white")
        text_col.pack(side="left", fill="both", expand=True)

        tk.Label(text_col, text=title, font=("Segoe UI", 9, "bold"), bg="white", fg="#6B7280").pack(anchor="w")
        lbl = tk.Label(text_col, text=value_text, font=("Segoe UI", 20, "bold"), bg="white", fg=COLOR_DARK)
        lbl.pack(anchor="w", pady=(2, 0))
        return lbl

    count_label = stat_card(stats_frame, "TOTAL BOOKINGS", "0", "📅", COLOR_ACCENT)
    revenue_label = stat_card(stats_frame, "TOTAL REVENUE", "₱0", "₱", COLOR_SUCCESS)
    guests_count_label = stat_card(stats_frame, "TOTAL GUESTS", "0", "👥", "#F5A623")

    # MINI ANALYTICS CHART
    chart_card = tk.Frame(main_frame, bg="white", highlightbackground="#E5E7EB", highlightthickness=1)
    chart_card.pack(fill="x", padx=30, pady=(0, 6))

    chart_header = tk.Frame(chart_card, bg="white")
    chart_header.pack(fill="x", padx=20, pady=(15, 5))

    tk.Label(
        chart_header, text="📊", font=("Segoe UI Emoji", 13), bg="white"
    ).pack(side="left", padx=(0, 8))
    tk.Label(
        chart_header, text="Bookings by Occasion", font=("Segoe UI", 12, "bold"),
        bg="white", fg=COLOR_DARK
    ).pack(side="left")
    tk.Label(
        chart_header, text="  •  live overview of your reservations", font=("Segoe UI", 9),
        bg="white", fg=COLOR_MUTED
    ).pack(side="left")

    chart_canvas = tk.Canvas(chart_card, width=1640, height=170, bg="white", highlightthickness=0)
    chart_canvas.pack(padx=20, pady=(0, 12), fill="x")

    # FORM CARD
    form_card = tk.Frame(main_frame, bg="white", highlightbackground="#E5E7EB", highlightthickness=1)
    form_card.pack(fill="x", padx=30, pady=(0, 6))
    for _col in range(4):
        form_card.grid_columnconfigure(_col, weight=1, uniform="form_col")

    tk.Label(form_card, text="Create New Reservation", font=("Segoe UI", 14, "bold"), bg="white", fg=COLOR_DARK).grid(row=0, column=0, columnspan=5, sticky="w", padx=20, pady=(12, 10))

    def create_label(text, r, c):
        tk.Label(form_card, text=text, font=("Segoe UI", 9, "bold"), bg="white", fg="#4B5563").grid(row=r, column=c, sticky="w", padx=(20 if c == 0 else 10, 15), pady=(5, 0))

    name_entry = tk.Entry(form_card, font=("Segoe UI", 11), bd=1, relief="solid")
    contact_entry = tk.Entry(form_card, font=("Segoe UI", 11), bd=1, relief="solid")

    create_label("Customer Name", 1, 0)
    add_placeholder(name_entry, "Enter customer name")
    name_entry.grid(row=2, column=0, padx=(20, 15), pady=5, sticky="ew")

    create_label("Contact Number", 1, 1)
    add_placeholder(contact_entry, "e.g. 0917 123 4567")

    create_label("Occasion", 1, 2)
    contact_entry.grid(row=2, column=1, padx=(10, 15), pady=5, sticky="ew")
    occasion_combo = ttk.Combobox(form_card, state="readonly", values=list(packages.keys()))
    occasion_combo.set("Select occasion")
    occasion_combo.grid(row=2, column=2, padx=(10, 15), pady=5, sticky="ew")
    occasion_combo.bind("<<ComboboxSelected>>", update_packages)

    create_label("Package", 1, 3)
    package_combo = ttk.Combobox(form_card, state="readonly")
    package_combo.set("Select package")
    package_combo.grid(row=2, column=3, padx=(10, 15), pady=5, sticky="ew")
    package_combo.bind("<<ComboboxSelected>>", update_price_preview)

    create_label("Date (MM/DD/YYYY)", 3, 0)
    date_entry = tk.Entry(form_card, font=("Segoe UI", 11), bd=1, relief="solid")
    add_placeholder(date_entry, "mm/dd/yyyy")
    date_entry.grid(row=4, column=0, padx=(20, 15), pady=5, sticky="ew")

    create_label("Time", 3, 1)
    time_entry = tk.Entry(form_card, font=("Segoe UI", 11), bd=1, relief="solid")
    add_placeholder(time_entry, "e.g. 10:00 AM")
    time_entry.grid(row=4, column=1, padx=(10, 15), pady=5, sticky="ew")

    create_label("Guests", 3, 2)
    guests_entry = tk.Entry(form_card, font=("Segoe UI", 11), bd=1, relief="solid")
    add_placeholder(guests_entry, "Number of guests")
    guests_entry.grid(row=4, column=2, padx=(10, 15), pady=5, sticky="ew")

    create_label(f"Discount Code ({DISCOUNT_CODE}=20% OFF)", 3, 3)
    discount_entry = tk.Entry(form_card, font=("Consolas", 11, "bold"), bd=1, relief="solid", fg=COLOR_DANGER)
    discount_entry.grid(row=4, column=3, padx=(10, 15), pady=5, sticky="ew")
    add_placeholder(discount_entry, "Enter discount code")
    discount_entry.bind("<KeyRelease>", update_price_preview)

    price_frame = tk.Frame(form_card, bg="white")
    price_frame.grid(row=5, column=0, columnspan=3, sticky="w", padx=20, pady=10)
    tk.Label(price_frame, text="Total Price:", font=("Segoe UI", 10, "bold"), bg="white").pack(side="left")
    price_label = tk.Label(price_frame, text="₱0", font=("Segoe UI", 14, "bold"), bg="white", fg=COLOR_ACCENT)
    price_label.pack(side="left", padx=10)

    create_btn = tk.Button(form_card, text="CREATE RESERVATION", bg=COLOR_ACCENT, fg="white", font=("Segoe UI", 10, "bold"), relief="flat", height=2, width=22, command=make_reservation, cursor="hand2")
    create_btn.grid(row=5, column=3, padx=20, pady=10, sticky="e")
    add_hover(create_btn, COLOR_ACCENT, COLOR_ACCENT_HOVER)

    clear_btn = tk.Button(form_card, text="CLEAR", bg="#E9EDF2", fg="#4B5563", font=("Segoe UI", 9, "bold"), relief="flat", command=clear_fields, cursor="hand2")
    clear_btn.grid(row=5, column=2, sticky="e", pady=10)
    add_hover(clear_btn, "#E9EDF2", "#D9DEE7")

    # TABLE
    list_header_row = tk.Frame(main_frame, bg=COLOR_BG)
    list_header_row.pack(fill="x", padx=30, pady=(8, 5))

    tk.Label(list_header_row, text="Reservation List - Green rows have discount applied", font=("Segoe UI", 12, "bold"), bg=COLOR_BG, fg=COLOR_DARK).pack(side="left")

    export_btn = tk.Button(list_header_row, text="📤 Export to Spreadsheet", bg="white", fg=COLOR_DARK, font=("Segoe UI", 9, "bold"), relief="flat", bd=1, highlightbackground="#D9DEE7", highlightthickness=1, command=export_to_spreadsheet, cursor="hand2")
    export_btn.pack(side="right", padx=(8, 0), ipady=4, ipadx=6)
    add_hover(export_btn, "white", "#F0F2F5")

    receipt_btn = tk.Button(list_header_row, text="🧾 Print Receipt", bg="white", fg=COLOR_DARK, font=("Segoe UI", 9, "bold"), relief="flat", bd=1, highlightbackground="#D9DEE7", highlightthickness=1, command=print_receipt, cursor="hand2")
    receipt_btn.pack(side="right", ipady=4, ipadx=6)
    add_hover(receipt_btn, "white", "#F0F2F5")

    table_frame = tk.Frame(main_frame, bg="white", highlightbackground="#E5E7EB", highlightthickness=1)
    table_frame.pack(padx=30, fill="both", expand=True, pady=(0, 10))

    cols = ("No.", "Name", "Contact", "Occasion", "Package", "Date", "Time", "Guests", "Total")
    reservation_table = ttk.Treeview(table_frame, columns=cols, show="headings", height=7)
    for col in cols:
        reservation_table.heading(col, text=col)
    reservation_table.column("No.", width=40, anchor="center")
    reservation_table.column("Name", width=150)
    reservation_table.pack(fill="both", expand=True, padx=10, pady=10)

    cancel_btn = tk.Button(main_frame, text="CANCEL SELECTED RESERVATION", bg=COLOR_DANGER, fg="white", font=("Segoe UI", 10, "bold"), relief="flat", width=32, height=2, command=cancel_reservation, cursor="hand2")
    cancel_btn.pack(pady=10)
    add_hover(cancel_btn, COLOR_DANGER, COLOR_DANGER_HOVER)

    load_reservations_from_db()
    update_table()
    update_chart()

    window.mainloop()

    # Close the database connection when the window is closed
    db_conn.close()


# ==========================================
# APP ENTRY POINT
# ==========================================
show_login_screen()