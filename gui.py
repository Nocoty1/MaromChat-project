"""
gui.py
ממשק המשתמש הגרפי של מערכת MaromChat.

קובץ זה אחראי על:
- הצגת מסך בית, התחברות והרשמה.
- הצגת המסך הראשי של הצ׳אטים.
- ניהול רשימות חברים, קבוצות וצ׳אטים.
- שליחת הודעות דרך client.py.
- קבלת הודעות מהשרת ועדכון המסך.
- העלאת תמונות פרופיל ותמונות קבוצה בפורמט Base64.
- הצגת הודעות שלא נקראו.

הקובץ משתמש בספריות מובנות בלבד:
base64, tkinter, messagebox, filedialog.
"""

import base64
import tkinter as tk
from tkinter import messagebox, filedialog
from client import MaromChatClient


class ChatGUI:
    """
    מחלקה ראשית שאחראית על כל ממשק המשתמש של MaromChat.
    המחלקה בונה את המסכים, שולחת בקשות דרך client.py,
    ומעדכנת את התצוגה לפי הודעות שמתקבלות מהשרת.
    """
    def __init__(self):
        """
        פעולה בונה של המחלקה.
        מאתחלת את חלון Tkinter, משתני המערכת, רשימות שמורות בזיכרון,
        קאש תמונות, ולאחר מכן מציגה את מסך הבית.
        """
        self.root = tk.Tk()
        self.root.title("MaromChat")
        self.root.geometry("1000x620")
        self.root.configure(bg="#0b141a")

        self.client = None
        self.username = None
        self.current_group = None
        self.current_display_name = None

        self.my_profile_img_b64 = ""

        self.cached_friends = []
        self.cached_groups = []
        self.unread = {}
        self.last_search_user = ""

        self.active_list = "chats"

        self.btn_chats = None
        self.btn_groups = None
        self.btn_friends = None
        self.e_filter = None
        self.e_group = None
        self.items_frame = None
        self.items_canvas = None
        self.chat_area = None
        self.e_msg = None
        self.lbl_group = None
        self.btn_invite_existing = None
        self.btn_leave_group = None
        self.btn_group_image = None
        self.req_box = None
        self.lbl_search_res = None
        self.e_search = None
        self.header_avatar_label = None
        self.my_profile_label = None
        self.is_opening_chat = False
        self.last_friends_hash = ""
        self.last_groups_hash = ""
        self.image_cache = {}

        # global images stay alive: profile + opened chat header
        self.image_refs = []

        # list images are only for sidebar rows
        self.list_image_refs = []

        self.home_screen()
        self.root.mainloop()

    def clear(self):
        """
        מוחקת את כל הרכיבים מהחלון.
        משמשת לפני מעבר בין מסכים כדי שלא יישארו רכיבים ממסך קודם.
        """
        for widget in self.root.winfo_children():
            widget.destroy()

    def ensure_client(self):
        """
        יוצרת אובייקט לקוח אם עדיין לא קיים.
        כך נפתח חיבור לשרת רק כאשר המשתמש באמת מבצע פעולה שדורשת תקשורת.
        """
        if self.client is None:
            self.client = MaromChatClient(self)

    def style_hover_button(self, widget, normal_bg: str, hover_bg: str):
        """
        מוסיפה אפקט מעבר עכבר לכפתור.
        הצבע משתנה כאשר העכבר מעל הכפתור וחוזר כאשר העכבר יוצא.
        """
        widget.configure(bg=normal_bg, activebackground=hover_bg)
        widget.bind("<Enter>", lambda e: widget.configure(bg=hover_bg))
        widget.bind("<Leave>", lambda e: widget.configure(bg=normal_bg))

    def reset_chat_view(self):
        """
        מאפסת את אזור הצ׳אט.
        משמשת כאשר המשתמש יוצא מקבוצה או כאשר אין צ׳אט פעיל להצגה.
        """
        self.current_group = None
        self.current_display_name = None
        self.lbl_group.config(text="Select a chat")

        if self.header_avatar_label is not None:
            self.header_avatar_label.delete("all")
            self.header_avatar_label.create_oval(4, 4, 44, 44, fill="#58636b", outline="")

        self.chat_area.config(state="normal")
        self.chat_area.delete("1.0", tk.END)
        self.chat_area.config(state="disabled")

        self.btn_invite_existing.config(state="disabled")
        self.btn_leave_group.config(state="disabled")
        self.btn_group_image.config(state="disabled")

    def choose_image_as_base64(self):
        """
        פותחת חלון בחירת קובץ וממירה את התמונה שנבחרה ל־Base64.
        Base64 מאפשר לשמור ולשלוח תמונה כטקסט דרך הפרוטוקול ומסד הנתונים.
        """
        path = filedialog.askopenfilename(
            title="Choose image",
            filetypes=[("PNG files", "*.png"), ("GIF files", "*.gif"), ("All files", "*.*")]
        )
        if not path:
            return None

        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception:
            messagebox.showerror("Error", "Could not read image file.")
            return None

    def photo_from_b64(self, img_b64: str, size: int = 50, keep: str = "global"):
        """
        מקבלת תמונה בפורמט Base64 ומחזירה אובייקט PhotoImage להצגה ב־Tkinter.
        הפעולה משתמשת ב־image_cache כדי למנוע טעינה חוזרת של אותה תמונה.
        """
        if not img_b64:
            return None

        key = f"{size}:{img_b64[:30]}"  # מפתח ייחודי

        #  אם כבר קיים — מחזירים ישר
        if key in self.image_cache:
            return self.image_cache[key]

        try:
            img = tk.PhotoImage(data=img_b64)

            w = img.width()
            h = img.height()

            scale = max(w / size, h / size)

            if scale > 1:
                subsample = int(scale)
                if subsample < 1:
                    subsample = 1
                img = img.subsample(subsample, subsample)

            #  שומרים בקאש
            self.image_cache[key] = img

            return img

        except Exception:
            return None

    def refresh_my_profile_avatar(self):
        """
        מרעננת את תמונת הפרופיל של המשתמש המחובר.
        אם אין תמונה, מוצג עיגול ברירת מחדל.
        """
        if self.my_profile_label is None:
            return

        self.my_profile_label.delete("all")

        photo = self.photo_from_b64(self.my_profile_img_b64, 48, keep="global")

        if photo:
            self.my_profile_label.create_image(24, 24, image=photo)
            self.my_profile_label.image = photo
        else:
            self.my_profile_label.create_oval(4, 4, 44, 44, fill="#58636b", outline="")

    def current_chat_image_b64(self) -> str:
        """
        מחזירה את תמונת הצ׳אט הפתוח כרגע.
        בצ׳אט פרטי נלקחת תמונת החבר, ובקבוצה נלקחת תמונת הקבוצה.
        """
        if not self.current_group:
            return ""

        if self.current_group.startswith("dm:"):
            for item in self.cached_friends:
                username = item.get("username", "")
                dm_group = f"dm:{min(self.username, username)}:{max(self.username, username)}"
                if dm_group == self.current_group:
                    return item.get("img", "")
            return ""

        for item in self.cached_groups:
            if item.get("name") == self.current_group:
                return item.get("img", "")
        return ""

    def refresh_header_avatar(self):
        """
        מעדכנת את התמונה שמופיעה בכותרת הצ׳אט הפתוח.
        """
        if self.header_avatar_label is None:
            return

        self.header_avatar_label.delete("all")

        img_b64 = self.current_chat_image_b64()
        photo = self.photo_from_b64(img_b64, 48, keep="global")

        if photo:
            self.header_avatar_label.create_image(24, 24, image=photo)
            self.header_avatar_label.image = photo
        else:
            self.header_avatar_label.create_oval(4, 4, 44, 44, fill="#58636b", outline="")

    def home_screen(self):
        """
        מציגה את מסך הבית של האפליקציה.
        במסך זה המשתמש יכול לבחור בין התחברות להרשמה.
        """
        self.clear()

        container = tk.Frame(self.root, bg="#0b141a")
        container.pack(fill="both", expand=True)

        card = tk.Frame(container, bg="#111b21", highlightthickness=1, highlightbackground="#1f2c33")
        card.place(relx=0.5, rely=0.5, anchor="center", width=520, height=420)

        tk.Label(card, text="MaromChat", fg="white", bg="#111b21", font=("Arial", 30, "bold")).pack(pady=(40, 10))
        tk.Label(card, text="Chat the way you love", fg="#9aa4ad", bg="#111b21", font=("Arial", 11)).pack(pady=(0, 26))

        btn_login = tk.Button(card, text="Login", fg="white", bd=0, cursor="hand2",
                              command=self.login_screen, font=("Arial", 13, "bold"), width=18, pady=12)
        btn_login.pack(pady=(0, 12))
        self.style_hover_button(btn_login, "#1f2c33", "#2a3942")

        btn_register = tk.Button(card, text="Register", fg="white", bd=0, cursor="hand2",
                                 command=self.register_screen, font=("Arial", 13, "bold"), width=18, pady=12)
        btn_register.pack()
        self.style_hover_button(btn_register, "#1f2c33", "#2a3942")

        tk.Label(card, text="© MaromChat", fg="#6f7a83", bg="#111b21", font=("Arial", 10)).pack(side="bottom", pady=18)

    def build_auth_screen(self, title_text: str):
        """
        בונה מסך משותף להתחברות ולהרשמה.
        מחזירה את הכרטיס ואת שדות שם המשתמש והסיסמה.
        """
        self.clear()

        container = tk.Frame(self.root, bg="#0b141a")
        container.pack(fill="both", expand=True)

        card = tk.Frame(container, bg="#111b21", highlightthickness=1, highlightbackground="#1f2c33")
        card.place(relx=0.5, rely=0.5, anchor="center", width=560, height=460)

        top = tk.Frame(card, bg="#111b21")
        top.pack(fill="x", padx=20, pady=(18, 0))

        btn_back = tk.Button(top, text="← Back", fg="white", bd=0, cursor="hand2",
                             command=self.home_screen, padx=10, pady=8)
        btn_back.pack(side="left")
        self.style_hover_button(btn_back, "#1f2c33", "#2a3942")

        tk.Label(top, text="MaromChat", fg="white", bg="#111b21", font=("Arial", 14, "bold")).pack(side="right")
        tk.Label(card, text=title_text, fg="white", bg="#111b21", font=("Arial", 22, "bold")).pack(pady=(22, 8))

        form = tk.Frame(card, bg="#111b21")
        form.pack(pady=10)

        tk.Label(form, text="Username", fg="#cfd7de", bg="#111b21").grid(row=0, column=0, sticky="w", pady=(0, 6))
        entry_user = tk.Entry(form, width=34, bg="#0b141a", fg="white",
                              insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#1f2c33")
        entry_user.grid(row=1, column=0, ipady=8, pady=(0, 14))

        tk.Label(form, text="Password", fg="#cfd7de", bg="#111b21").grid(row=2, column=0, sticky="w", pady=(0, 6))
        entry_pass = tk.Entry(form, show="*", width=34, bg="#0b141a", fg="white",
                              insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#1f2c33")
        entry_pass.grid(row=3, column=0, ipady=8, pady=(0, 10))

        return card, entry_user, entry_pass

    def login_screen(self):
        """
        מציגה את מסך ההתחברות.
        לאחר מילוי שם משתמש וסיסמה נשלחת בקשת LOGIN לשרת.
        """
        card, entry_user, entry_pass = self.build_auth_screen("Login")

        def do_login():
            username = entry_user.get().strip()
            password = entry_pass.get().strip()
            if not username or not password:
                messagebox.showerror("Error", "Enter username and password.")
                return
            self.ensure_client()
            self.username = username
            self.client.login(username, password)

        btn = tk.Button(card, text="Login", fg="white", bd=0, cursor="hand2",
                        command=do_login, font=("Arial", 13, "bold"), padx=18, pady=12)
        btn.pack(pady=(10, 6))
        self.style_hover_button(btn, "#00a884", "#00c49a")

    def register_screen(self):
        """
        מציגה את מסך ההרשמה.
        לאחר מילוי שם משתמש וסיסמה נשלחת בקשת REGISTER לשרת.
        """
        card, entry_user, entry_pass = self.build_auth_screen("Register")

        def do_register():
            username = entry_user.get().strip()
            password = entry_pass.get().strip()
            if not username or not password:
                messagebox.showerror("Error", "Enter username and password.")
                return
            self.ensure_client()
            self.username = username
            self.client.register(username, password)

        btn = tk.Button(card, text="Create account", fg="white", bd=0, cursor="hand2",
                        command=do_register, font=("Arial", 13, "bold"), padx=18, pady=12)
        btn.pack(pady=(10, 6))
        self.style_hover_button(btn, "#1f2c33", "#2a3942")

    def chat_screen(self):
        """
        מציגה את המסך הראשי לאחר התחברות.
        המסך כולל רשימת צ׳אטים, קבוצות, חברים, אזור הודעות ושדה כתיבה.
        """
        self.clear()

        left = tk.Frame(self.root, bg="#111b21", width=360)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        top = tk.Frame(left, bg="#1f2c33", height=56)
        top.pack(fill="x")
        top.pack_propagate(False)

        self.my_profile_label = tk.Canvas(top, width=48, height=48, bg="#1f2c33", highlightthickness=0)
        self.my_profile_label.pack(side="left", padx=(10, 4), pady=4)
        self.my_profile_label.create_oval(4, 4, 44, 44, fill="#58636b", outline="")

        tk.Label(top, text=self.username or "User", fg="white", bg="#1f2c33",
                 font=("Arial", 12, "bold")).pack(side="left", padx=8)

        btn_profile_img = tk.Button(top, text="Profile Image", fg="white", bd=0, cursor="hand2",
                                    command=self.set_my_profile_image, padx=12, pady=8)
        btn_profile_img.pack(side="right", padx=10, pady=8)
        self.style_hover_button(btn_profile_img, "#1f2c33", "#2a3942")

        tabs = tk.Frame(left, bg="#111b21")
        tabs.pack(fill="x", pady=(10, 0))

        self.btn_chats = tk.Button(tabs, text="Chats", fg="white", bd=0, cursor="hand2",
                                   command=self.show_chats, padx=12, pady=8)
        self.btn_chats.pack(side="left", padx=(10, 6))

        self.btn_groups = tk.Button(tabs, text="Groups", fg="white", bd=0, cursor="hand2",
                                    command=self.show_groups, padx=12, pady=8)
        self.btn_groups.pack(side="left", padx=(0, 6))

        self.btn_friends = tk.Button(tabs, text="Friends", fg="white", bd=0, cursor="hand2",
                                     command=self.show_friends, padx=12, pady=8)
        self.btn_friends.pack(side="left")

        search_wrap = tk.Frame(left, bg="#111b21")
        search_wrap.pack(fill="x", padx=10, pady=(10, 8))

        self.e_filter = tk.Entry(search_wrap, bg="#0b141a", fg="white",
                                 insertbackground="white", bd=0, highlightthickness=1,
                                 highlightbackground="#1f2c33")
        self.e_filter.pack(fill="x", ipady=8)
        self.e_filter.bind("<KeyRelease>", lambda e: self.redraw_current_list_only())

        items_container = tk.Frame(left, bg="#111b21")
        items_container.pack(fill="both", expand=True)

        self.items_canvas = tk.Canvas(items_container, bg="#111b21", highlightthickness=0)
        scrollbar = tk.Scrollbar(items_container, orient="vertical", command=self.items_canvas.yview)
        self.items_frame = tk.Frame(self.items_canvas, bg="#111b21")

        self.items_frame.bind(
            "<Configure>",
            lambda e: self.items_canvas.configure(scrollregion=self.items_canvas.bbox("all"))
        )
        self.items_canvas.create_window((0, 0), window=self.items_frame, anchor="nw")
        self.items_canvas.configure(yscrollcommand=scrollbar.set)

        self.items_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        actions = tk.Frame(left, bg="#111b21")
        actions.pack(fill="x", padx=10, pady=(8, 10))

        self.e_group = tk.Entry(actions, bg="#0b141a", fg="white",
                                insertbackground="white", bd=0, highlightthickness=1,
                                highlightbackground="#1f2c33")
        self.e_group.pack(side="left", fill="x", expand=True, ipady=7)

        btn_create = tk.Button(actions, text="Create", fg="white", bd=0, cursor="hand2",
                               command=self.create_group, padx=10, pady=8)
        btn_create.pack(side="left", padx=(8, 4))
        self.style_hover_button(btn_create, "#1f2c33", "#2a3942")

        btn_create_invite = tk.Button(actions, text="Create + Invite", fg="white", bd=0, cursor="hand2",
                                      command=self.create_group_invite, padx=10, pady=8)
        btn_create_invite.pack(side="left", padx=(0, 4))
        self.style_hover_button(btn_create_invite, "#1f2c33", "#2a3942")

        btn_join = tk.Button(actions, text="Join", fg="white", bd=0, cursor="hand2",
                             command=self.join_group, padx=10, pady=8)
        btn_join.pack(side="left")
        self.style_hover_button(btn_join, "#1f2c33", "#2a3942")

        right = tk.Frame(self.root, bg="#0b141a")
        right.pack(side="right", fill="both", expand=True)

        header = tk.Frame(right, bg="#1f2c33", height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        self.header_avatar_label = tk.Canvas(header, width=48, height=48, bg="#1f2c33", highlightthickness=0)
        self.header_avatar_label.pack(side="left", padx=(10, 0), pady=4)
        self.header_avatar_label.create_oval(4, 4, 44, 44, fill="#58636b", outline="")

        self.lbl_group = tk.Label(header, text="Select a chat", fg="white", bg="#1f2c33",
                                  font=("Arial", 12, "bold"), padx=12, pady=12)
        self.lbl_group.pack(side="left")

        self.btn_group_image = tk.Button(header, text="Group Image", fg="white", bd=0, cursor="hand2",
                                         command=self.set_current_group_image, padx=12, pady=8)
        self.btn_group_image.pack(side="right", padx=(4, 10), pady=8)
        self.style_hover_button(self.btn_group_image, "#1f2c33", "#2a3942")
        self.btn_group_image.config(state="disabled")

        self.btn_leave_group = tk.Button(header, text="Leave", fg="white", bd=0, cursor="hand2",
                                         command=self.leave_current_group, padx=12, pady=8)
        self.btn_leave_group.pack(side="right", padx=(4, 10), pady=8)
        self.style_hover_button(self.btn_leave_group, "#1f2c33", "#2a3942")
        self.btn_leave_group.config(state="disabled")

        self.btn_invite_existing = tk.Button(header, text="Invite", fg="white", bd=0, cursor="hand2",
                                             command=self.invite_to_current_group, padx=12, pady=8)
        self.btn_invite_existing.pack(side="right", padx=10, pady=8)
        self.style_hover_button(self.btn_invite_existing, "#1f2c33", "#2a3942")
        self.btn_invite_existing.config(state="disabled")

        self.chat_area = tk.Text(right, state="disabled", bg="#0b141a", fg="white",
                                 insertbackground="white", bd=0, padx=12, pady=12, wrap="word")
        self.chat_area.pack(fill="both", expand=True)

        bottom = tk.Frame(right, bg="#111b21")
        bottom.pack(fill="x")

        self.e_msg = tk.Entry(bottom, bg="#0b141a", fg="white", insertbackground="white",
                              bd=0, highlightthickness=1, highlightbackground="#1f2c33")
        self.e_msg.pack(side="left", fill="x", expand=True, padx=10, pady=10, ipady=8)
        self.e_msg.bind("<Return>", lambda e: self.send_message())

        btn_send = tk.Button(bottom, text="Send", fg="white", bd=0, cursor="hand2",
                             command=self.send_message, padx=16, pady=10)
        btn_send.pack(side="right", padx=10, pady=10)
        self.style_hover_button(btn_send, "#00a884", "#00c49a")

        self.show_chats()

    def set_active_tab(self, tab_name: str):
        """
        מסמנת איזה טאב פעיל כרגע: chats, groups או friends.
        הטאב הפעיל מקבל צבע שונה.
        """
        normal = "#1f2c33"
        hover = "#2a3942"
        active = "#00a884"

        for button in (self.btn_chats, self.btn_groups, self.btn_friends):
            self.style_hover_button(button, normal, hover)

        if tab_name == "chats":
            self.style_hover_button(self.btn_chats, active, "#00c49a")
        elif tab_name == "groups":
            self.style_hover_button(self.btn_groups, active, "#00c49a")
        elif tab_name == "friends":
            self.style_hover_button(self.btn_friends, active, "#00c49a")

    def clear_items(self):
        """
        מנקה את רשימת הפריטים בצד שמאל לפני ציור מחדש.
        """
        self.list_image_refs = []

        for widget in self.items_frame.winfo_children():
            widget.destroy()

    def add_list_row(self, title: str, subtitle: str, on_click,
                     badge: str = "", unread_count: int = 0,
                     img_b64: str = ""):

        row = tk.Frame(self.items_frame, bg="#111b21")
        row.pack(fill="x", padx=8, pady=4)

        card = tk.Frame(row, bg="#111b21", highlightthickness=1, highlightbackground="#1f2c33")
        card.pack(fill="x")

        inner = tk.Frame(card, bg="#111b21")
        inner.pack(fill="x", padx=10, pady=10)

        photo = self.photo_from_b64(img_b64, 50, keep="list")

        canvas = tk.Canvas(inner, width=50, height=50, bg="#111b21", highlightthickness=0)

        if photo:
            canvas.create_image(25, 25, image=photo)
            canvas.image = photo
        else:
            canvas.create_oval(5, 5, 45, 45, fill="#58636b", outline="")

        canvas.pack(side="left", padx=(0, 12))
        avatar = canvas

        textcol = tk.Frame(inner, bg="#111b21")
        textcol.pack(side="left", fill="x", expand=True)

        top_line = tk.Frame(textcol, bg="#111b21")
        top_line.pack(fill="x")

        lbl_title = tk.Label(top_line, text=title, fg="white",
                             bg="#111b21", font=("Arial", 12, "bold"))
        lbl_title.pack(side="left")

        if badge:
            badge_label = tk.Label(top_line, text=badge, fg="#cfd7de",
                                   bg="#1f2c33", font=("Arial", 9, "bold"),
                                   padx=8, pady=2)
            badge_label.pack(side="left", padx=(8, 0))

        unread_label = None
        if unread_count > 0:
            unread_label = tk.Label(top_line, text=f"● {unread_count}",
                                    fg="#00c49a", bg="#111b21",
                                    font=("Arial", 10, "bold"))
            unread_label.pack(side="right", padx=(0, 8))

        lbl_sub = tk.Label(textcol, text=subtitle,
                           fg="#9aa4ad", bg="#111b21",
                           font=("Arial", 10))
        lbl_sub.pack(anchor="w", pady=(4, 0))

        def set_bg(bg):
            for w in (row, card, inner, textcol, top_line,
                      avatar, lbl_title, lbl_sub):
                w.config(bg=bg)
            if unread_label:
                unread_label.config(bg=bg)

        def on_enter(_):
            set_bg("#1f2c33")

        def on_leave(_):
            set_bg("#111b21")

        for widget in (row, card, inner, textcol,
                       top_line, avatar, lbl_title, lbl_sub):
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", lambda e: on_click())

    def redraw_current_list_only(self):
        """
        מציירת מחדש רק את הרשימה הפעילה כרגע.
        פעולה זו מונעת רענון מיותר של כל המסך.
        """
        if self.active_list == "groups":
            self.render_groups_list()
        elif self.active_list == "chats":
            self.render_chats_list()

    def render_chats_list(self):
        """
        מציגה את רשימת הצ׳אטים הפרטיים לפי רשימת החברים.
        לכל צ׳אט ניתן להציג גם מונה unread.
        """
        self.clear_items()
        filter_text = self.e_filter.get().strip().lower()

        if not self.cached_friends:
            tk.Label(self.items_frame, text="No friends yet. Go to Friends and send a request.",
                     fg="#cfd7de", bg="#111b21").pack(anchor="w", padx=10, pady=10)
            return

        for friend_data in self.cached_friends:
            friend = friend_data["username"]
            img_b64 = friend_data["img"]

            if filter_text and filter_text not in friend.lower():
                continue

            dm_unread = 0
            for group_name, count in self.unread.items():
                if group_name.startswith("dm:") and count > 0:
                    if group_name.endswith(":" + friend) or group_name.startswith("dm:" + friend + ":"):
                        dm_unread += count

            self.add_list_row(
                title=friend,
                subtitle="Direct chat",
                on_click=lambda username=friend: self.open_dm(username),
                badge="CHAT",
                unread_count=dm_unread,
                img_b64=img_b64
            )

    def render_groups_list(self):
        """
        מציגה את רשימת הקבוצות של המשתמש.
        צ׳אטים פרטיים שמתחילים ב־dm לא מוצגים ברשימת הקבוצות.
        """
        self.clear_items()
        filter_text = self.e_filter.get().strip().lower()

        if not self.cached_groups:
            tk.Label(self.items_frame, text="No groups yet. Create or join one.",
                     fg="#cfd7de", bg="#111b21").pack(anchor="w", padx=10, pady=10)
            return

        for group_data in self.cached_groups:
            group_name = group_data["name"]
            img_b64 = group_data["img"]

            if group_name.startswith("dm:"):
                continue
            if filter_text and filter_text not in group_name.lower():
                continue

            self.add_list_row(
                title=group_name,
                subtitle="Group",
                on_click=lambda name=group_name: self.open_group(name, name),
                badge="GROUP",
                unread_count=self.unread.get(group_name, 0),
                img_b64=img_b64
            )

    def show_chats(self):
        """
        עוברת לטאב הצ׳אטים הפרטיים ומבקשת מהשרת חברים ו־unread.
        """
        self.active_list = "chats"
        self.set_active_tab("chats")
        self.ensure_client()
        self.client.get_friends()
        self.client.unread_all()

    def show_groups(self):
        """
        עוברת לטאב הקבוצות ומבקשת מהשרת את קבוצות המשתמש ו־unread.
        """
        self.active_list = "groups"
        self.set_active_tab("groups")
        self.ensure_client()
        self.client.my_groups()
        self.client.unread_all()

    def show_friends(self):
        """
        מציגה את מסך החברים.
        במסך זה ניתן לחפש משתמשים, לשלוח בקשות חברות ולאשר בקשות נכנסות.
        """
        self.active_list = "friends"
        self.set_active_tab("friends")
        self.clear_items()
        self.ensure_client()

        header = tk.Label(self.items_frame, text="Friends", fg="white", bg="#111b21", font=("Arial", 14, "bold"))
        header.pack(anchor="w", padx=10, pady=(10, 6))

        row = tk.Frame(self.items_frame, bg="#111b21")
        row.pack(fill="x", padx=10, pady=(0, 8))

        self.e_search = tk.Entry(row, bg="#0b141a", fg="white",
                                 insertbackground="white", bd=0, highlightthickness=1,
                                 highlightbackground="#1f2c33")
        self.e_search.pack(side="left", fill="x", expand=True, ipady=7)

        btn_find = tk.Button(row, text="Search", fg="white", bd=0, cursor="hand2",
                             command=lambda: self.client.search_user(self.e_search.get().strip()),
                             padx=10, pady=8)
        btn_find.pack(side="left", padx=(8, 0))
        self.style_hover_button(btn_find, "#1f2c33", "#2a3942")

        self.lbl_search_res = tk.Label(self.items_frame, text="", fg="#cfd7de", bg="#111b21")
        self.lbl_search_res.pack(anchor="w", padx=10)

        btn_send_req = tk.Button(self.items_frame, text="Send Friend Request", fg="white", bd=0, cursor="hand2",
                                 command=self.send_request_from_last_search, padx=10, pady=8)
        btn_send_req.pack(anchor="w", padx=10, pady=(6, 10))
        self.style_hover_button(btn_send_req, "#00a884", "#00c49a")

        req_hdr = tk.Label(self.items_frame, text="Incoming Requests", fg="white", bg="#111b21", font=("Arial", 12, "bold"))
        req_hdr.pack(anchor="w", padx=10, pady=(8, 4))

        self.req_box = tk.Frame(self.items_frame, bg="#111b21")
        self.req_box.pack(fill="x", padx=10, pady=(0, 6))

        self.client.get_friend_requests()
        self.client.get_friends()

    def set_my_profile_image(self):
        """
        מאפשרת לבחור תמונת פרופיל, להציג אותה מיד ולשלוח אותה לשרת.
        """
        img_b64 = self.choose_image_as_base64()
        if img_b64:
            self.my_profile_img_b64 = img_b64
            self.refresh_my_profile_avatar()
            self.client.set_profile_image(img_b64)

    def set_current_group_image(self):
        """
        מאפשרת להעלות תמונה לקבוצה הפתוחה כרגע.
        הפעולה אינה זמינה בצ׳אט פרטי.
        """
        if not self.current_group or self.current_group.startswith("dm:"):
            return
        img_b64 = self.choose_image_as_base64()
        if img_b64:
            self.client.set_group_image(self.current_group, img_b64)

    def send_request_from_last_search(self):
        """
        שולחת בקשת חברות למשתמש האחרון שנמצא בחיפוש.
        """
        if not self.last_search_user:
            messagebox.showerror("Error", "Search for an existing user first.")
            return
        self.client.send_friend_request(self.last_search_user)

    def create_group(self):
        """
        יוצרת קבוצה חדשה לפי השם שהוזן בשדה הקבוצה.
        """
        name = self.e_group.get().strip()
        if name:
            self.client.create_group(name)

    def create_group_invite(self):
        """
        יוצרת קבוצה חדשה ומאפשרת לבחור חברים להזמנה.
        """
        name = self.e_group.get().strip()
        if not name:
            messagebox.showerror("Error", "Enter a group name first.")
            return

        self.open_member_picker_window(
            title="Invite Friends",
            headline=f"Create group: {name}",
            confirm_text="Create",
            confirm_callback=lambda members: self.client.create_group_with_friends(name, members)
        )

    def join_group(self):
        """
        שולחת בקשה להצטרפות לקבוצה לפי שם שהוזן.
        """
        name = self.e_group.get().strip()
        if name:
            self.client.join_group(name)

    def invite_to_current_group(self):
        """
        מזמינה חברים לקבוצה הפתוחה כרגע.
        פעולה זו זמינה רק בקבוצה ולא בצ׳אט פרטי.
        """
        if not self.current_group or self.current_group.startswith("dm:"):
            return

        self.open_member_picker_window(
            title="Invite Friends to Group",
            headline=f"Invite to: {self.current_group}",
            confirm_text="Invite",
            confirm_callback=lambda members: self.client.invite_group(self.current_group, members)
        )

    def leave_current_group(self):
        """
        מאפשרת למשתמש לצאת מהקבוצה הפתוחה לאחר אישור.
        """
        if not self.current_group or self.current_group.startswith("dm:"):
            return
        confirmed = messagebox.askyesno("Leave Group", f"Leave '{self.current_group}'?")
        if confirmed:
            self.client.leave_group(self.current_group)

    def open_member_picker_window(self, title: str, headline: str, confirm_text: str, confirm_callback):
        """
        פותחת חלון בחירת חברים מתוך רשימת החברים.
        משמשת להזמנת חברים לקבוצה או ליצירת קבוצה עם חברים.
        """
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("360x420")
        win.configure(bg="#111b21")

        tk.Label(win, text=headline, fg="white", bg="#111b21", font=("Arial", 12, "bold")).pack(pady=(10, 6))

        lst = tk.Listbox(win, selectmode="multiple", bg="#0b141a", fg="white",
                         highlightthickness=1, highlightbackground="#1f2c33")
        lst.pack(fill="both", expand=True, padx=10, pady=10)

        usernames = [f["username"] for f in self.cached_friends]
        for friend in usernames:
            lst.insert("end", friend)

        def do_confirm():
            selected = [usernames[i] for i in lst.curselection()]
            confirm_callback(selected)
            win.destroy()

        btn = tk.Button(win, text=confirm_text, fg="white", bd=0, cursor="hand2",
                        command=do_confirm, padx=14, pady=10)
        btn.pack(pady=(0, 12))
        self.style_hover_button(btn, "#00a884", "#00c49a")

    def open_group(self, group_name: str, display_title: str = None):
        """
        פותחת צ׳אט או קבוצה.
        מעדכנת כותרת, תמונה, כפתורי פעולה, טוענת היסטוריה ומסמנת כנקרא.
        """
        self.is_opening_chat = True

        self.current_group = group_name
        self.current_display_name = display_title or group_name
        self.lbl_group.config(text=self.current_display_name)

        is_real_group = bool(group_name and not group_name.startswith("dm:"))
        self.btn_invite_existing.config(state="normal" if is_real_group else "disabled")
        self.btn_leave_group.config(state="normal" if is_real_group else "disabled")
        self.btn_group_image.config(state="normal" if is_real_group else "disabled")

        # מציג מיד את התמונה והשם בלי לחכות לרענון מהשרת
        self.refresh_header_avatar()

        self.chat_area.config(state="normal")
        self.chat_area.delete("1.0", tk.END)
        self.chat_area.config(state="disabled")

        self.client.load_history(group_name)
        self.client.mark_read(group_name)

        # נותן למסך להיפתח קודם, ורק אז מרענן unread
        self.root.after(300, self.finish_opening_chat)

    def open_dm(self, friend_username: str):
        """
        מבקשת מהשרת לפתוח צ׳אט פרטי עם חבר.
        """
        self.client.open_dm(friend_username)

    def finish_opening_chat(self):
        """
        מסיימת את תהליך פתיחת הצ׳אט ומרעננת unread לאחר השהיה קצרה.
        """
        self.is_opening_chat = False
        self.client.unread_all()

    def send_message(self):
        """
        שולחת את ההודעה שנכתבה לצ׳אט הפתוח.
        אם אין צ׳אט פתוח או שההודעה ריקה, לא נשלח דבר.
        """
        if not self.current_group:
            messagebox.showerror("Error", "Select a chat first.")
            return
        text = self.e_msg.get().strip()
        if not text:
            return
        self.client.send_message(self.current_group, text)
        self.e_msg.delete(0, tk.END)

    def parse_group_name_from_message(self, line: str):
        """
        מחלצת שם קבוצה מתוך הודעה בפורמט:
        [group_name] sender: message
        """
        if line.startswith("[") and "]" in line:
            return line[1:line.index("]")]
        return None

    def receive_message(self, msg: str):
        """
        מטפלת בכל הודעה שמגיעה מהשרת.
        בהתאם לסוג ההודעה היא מעדכנת מסכים, מציגה הודעות,
        מרעננת רשימות, מעדכנת unread ומציגה הודעות שגיאה או הצלחה.
        """
        if msg == "LOGIN_OK":
            self.chat_screen()
            self.client.get_my_profile_image()
            if msg.startswith("UNREAD_ALL|"):
                packed = msg.split("|", 1)[1].strip()
                self.unread = {}

                if packed:
                    for part in packed.split(","):
                        if "=" in part:
                            group_name, count = part.split("=", 1)
                            try:
                                self.unread[group_name] = int(count)
                            except ValueError:
                                pass

                if self.current_group in self.unread:
                    self.unread.pop(self.current_group, None)

                # לא מרעננים את הרשימה בזמן פתיחת צ׳אט כדי למנוע הבהוב
                if not self.is_opening_chat:
                    self.redraw_current_list_only()

                return

        if msg == "LOGIN_FAIL":
            messagebox.showerror("Error", "Invalid username or password.")
            return

        if msg == "REG_OK":
            messagebox.showinfo("OK", "Registered successfully. Now login.")
            return

        if msg == "REG_FAIL":
            messagebox.showerror("Error", "Username already exists.")
            return

        if msg.startswith("MY_PROFILE_IMG|"):
            self.my_profile_img_b64 = msg.split("|", 1)[1]
            self.refresh_my_profile_avatar()
            return

        if msg == "PROFILE_IMG_OK":
            messagebox.showinfo("Profile", "Profile image updated.")
            self.client.get_my_profile_image()
            self.client.get_friends()
            return

        if msg == "PROFILE_IMG_FAIL":
            messagebox.showerror("Profile", "Could not update profile image.")
            return

        if msg == "GROUP_IMG_OK":
            messagebox.showinfo("Group", "Group image updated.")
            self.client.my_groups()
            self.refresh_header_avatar()
            return

        if msg == "GROUP_IMG_FAIL":
            messagebox.showerror("Group", "Could not update group image.")
            return

        if msg == "FRIEND_REQUESTS_UPDATED":
            if self.active_list == "friends":
                self.client.get_friend_requests()
            return

        if msg == "FRIENDS_UPDATED":
            self.client.get_friends()
            if self.active_list == "chats":
                self.client.unread_all()
            self.refresh_header_avatar()
            return

        if msg.startswith("INVITE_OK|"):
            added = msg.split("|", 1)[1]
            messagebox.showinfo("Invite", f"Invited: {added}")
            if self.active_list == "groups":
                self.client.my_groups()
            return

        if msg.startswith("INVITE_FAIL"):
            messagebox.showerror("Invite", msg)
            return

        if msg == "LEAVE_OK":
            messagebox.showinfo("Group", "You left the group.")
            self.reset_chat_view()
            self.client.my_groups()
            self.client.unread_all()
            return

        if msg == "LEAVE_FAIL":
            messagebox.showerror("Group", "Could not leave the group.")
            return

        if msg.startswith("UNREAD_ALL|"):
            packed = msg.split("|", 1)[1].strip()
            self.unread = {}

            if packed:
                for part in packed.split(","):
                    if "=" in part:
                        group_name, count = part.split("=", 1)
                        try:
                            self.unread[group_name] = int(count)
                        except ValueError:
                            pass

            if self.current_group in self.unread:
                self.unread.pop(self.current_group, None)

            self.redraw_current_list_only()
            return

        if msg.startswith("MYGROUPS|"):
            packed = msg.split("|", 1)[1]

            # אם לא השתנה — לא מרעננים
            if packed == self.last_groups_hash:
                return

            self.last_groups_hash = packed

            items = [x for x in packed.split(",") if x.strip()] if packed else []

            parsed = []
            for item in items:
                parts = item.split("::", 2)
                name = parts[0] if len(parts) > 0 else ""
                img = parts[1] if len(parts) > 1 else ""
                parsed.append({"name": name, "img": img})

            self.cached_groups = parsed

            if self.active_list == "groups":
                self.render_groups_list()

            return

        if msg.startswith("FRIENDS|"):
            packed = msg.split("|", 1)[1]

            # אם לא השתנה — לא מרעננים
            if packed == self.last_friends_hash:
                return

            self.last_friends_hash = packed

            items = [x for x in packed.split(",") if x.strip()] if packed else []

            parsed = []
            for item in items:
                parts = item.split("::", 2)
                username = parts[0] if len(parts) > 0 else ""
                img = parts[1] if len(parts) > 1 else ""
                parsed.append({"username": username, "img": img})

            self.cached_friends = parsed

            if self.active_list == "chats":
                self.render_chats_list()

            return

        if msg.startswith("DM_OK|"):
            parts = msg.split("|")
            if len(parts) >= 3:
                group_name = parts[1]
                friend = parts[2]
                self.open_group(group_name, friend)
            return

        if msg == "DM_FAIL":
            messagebox.showerror("Error", "You can only open a chat with a friend.")
            return

        if msg.startswith("SEARCH_RESULT|"):
            found_user = msg.split("|", 1)[1].strip()
            self.last_search_user = found_user
            self.lbl_search_res.config(text=("Found: " + found_user) if found_user else "No such user.")
            return

        if msg.startswith("FRIEND_REQUEST_RESULT|"):
            result = msg.split("|", 1)[1]
            messagebox.showinfo("Friend Request", result)
            return

        if msg.startswith("FRIEND_REQUESTS|"):
            if self.active_list != "friends":
                return

            packed = msg.split("|", 1)[1] if "|" in msg else ""

            for widget in self.req_box.winfo_children():
                widget.destroy()

            requests = [x for x in packed.split(",") if x.strip()] if packed else []
            if not requests:
                tk.Label(self.req_box, text="No requests.", fg="#cfd7de", bg="#111b21").pack(anchor="w")
                return

            for username in requests:
                line = tk.Frame(self.req_box, bg="#111b21")
                line.pack(fill="x", pady=2)

                tk.Label(line, text=username, fg="white", bg="#111b21").pack(side="left")

                btn = tk.Button(line, text="Accept", fg="white", bd=0, cursor="hand2",
                                command=lambda u=username: self.client.accept_friend(u),
                                padx=10, pady=6)
                btn.pack(side="right")
                self.style_hover_button(btn, "#00a884", "#00c49a")
            return

        if msg in ("FRIEND_ACCEPT_OK", "FRIEND_ACCEPT_FAIL"):
            messagebox.showinfo("Friends", msg)
            return

        if msg in ("GROUP_OK", "GROUP_EXISTS", "JOIN_OK", "MARK_READ_OK", "MARK_READ_FAIL"):
            if self.active_list == "groups":
                self.client.my_groups()
            if self.active_list == "chats":
                self.client.get_friends()
            if self.active_list == "friends":
                self.client.get_friend_requests()
                self.client.get_friends()
            self.client.unread_all()
            return

        group_name = self.parse_group_name_from_message(msg)

        if group_name:
            if group_name != self.current_group:
                self.client.unread_all()
                return

            self.chat_area.config(state="normal")
            self.chat_area.insert("end", msg + "\n")
            self.chat_area.config(state="disabled")
            self.chat_area.see("end")

            self.client.mark_read(group_name)
            self.unread.pop(group_name, None)
            self.redraw_current_list_only()
            return


if __name__ == "__main__":
    ChatGUI()
