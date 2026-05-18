import sqlite3
import threading
from security import hash_password


class Database:
    def __init__(self, db_path: str = "maromchat.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()
        self.create_tables()

    # =========================================================
    # TABLE SETUP
    # =========================================================
    def create_tables(self):
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                profile_img_b64 TEXT DEFAULT ''
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS groups(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                img_b64 TEXT DEFAULT ''
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS group_members(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT,
                username TEXT
            )
            """)

            cur.execute("""
            
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT,
                sender TEXT,
                content TEXT
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS friend_requests(
                from_user TEXT NOT NULL,
                to_user   TEXT NOT NULL,
                ts        DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(from_user, to_user)
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS friends(
                user_a TEXT NOT NULL,
                user_b TEXT NOT NULL,
                ts     DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_a, user_b)
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS last_read(
                username    TEXT NOT NULL,
                group_name  TEXT NOT NULL,
                last_msg_id INTEGER NOT NULL DEFAULT 0,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(username, group_name)
            )
            """)

            self.conn.commit()

    # =========================================================
    # HELPERS
    # =========================================================
    def normalize_friend_pair(self, user1: str, user2: str):
        return (user1, user2) if user1 < user2 else (user2, user1)

    # =========================================================
    # USERS
    # =========================================================
    def register_user(self, username: str, password: str) -> bool:
        with self.lock:
            try:
                self.conn.execute(
                    "INSERT INTO users(username, password) VALUES (?, ?)",
                    (username, hash_password(password))
                )
                self.conn.commit()
                return True
            except Exception:
                return False

    def validate_user(self, username: str, password: str) -> bool:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT 1 FROM users WHERE username=? AND password=?",
                (username, hash_password(password))
            )
            return cur.fetchone() is not None

    def user_exists(self, username: str) -> bool:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT 1 FROM users WHERE username=? LIMIT 1", (username,))
            return cur.fetchone() is not None

    def set_profile_image(self, username: str, img_b64: str) -> bool:
        with self.lock:
            try:
                self.conn.execute(
                    "UPDATE users SET profile_img_b64=? WHERE username=?",
                    (img_b64, username)
                )
                self.conn.commit()
                return True
            except Exception:
                return False

    def get_profile_image(self, username: str) -> str:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT profile_img_b64 FROM users WHERE username=?", (username,))
            row = cur.fetchone()
            return (row[0] or "") if row else ""

    # =========================================================
    # GROUPS
    # =========================================================
    def create_group(self, group_name: str) -> bool:
        with self.lock:
            try:
                self.conn.execute("INSERT INTO groups(name) VALUES (?)", (group_name,))
                self.conn.commit()
                return True
            except Exception:
                return False

    def ensure_group(self, group_name: str) -> bool:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT 1 FROM groups WHERE name=? LIMIT 1", (group_name,))
            if cur.fetchone():
                return True
            try:
                self.conn.execute("INSERT INTO groups(name) VALUES (?)", (group_name,))
                self.conn.commit()
                return True
            except Exception:
                return False

    def join_group(self, group_name: str, username: str) -> bool:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT 1 FROM group_members WHERE group_name=? AND username=?",
                (group_name, username)
            )
            if cur.fetchone():
                return True

            self.conn.execute(
                "INSERT INTO group_members(group_name, username) VALUES (?, ?)",
                (group_name, username)
            )
            self.conn.commit()
            return True

    def leave_group(self, group_name: str, username: str) -> bool:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "DELETE FROM group_members WHERE group_name=? AND username=?",
                (group_name, username)
            )
            removed = cur.rowcount > 0

            self.conn.execute(
                "DELETE FROM last_read WHERE group_name=? AND username=?",
                (group_name, username)
            )
            self.conn.commit()
            return removed

    def set_group_image(self, group_name: str, img_b64: str) -> bool:
        with self.lock:
            try:
                self.conn.execute(
                    "UPDATE groups SET img_b64=? WHERE name=?",
                    (img_b64, group_name)
                )
                self.conn.commit()
                return True
            except Exception:
                return False

    def get_group_image(self, group_name: str) -> str:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT img_b64 FROM groups WHERE name=?", (group_name,))
            row = cur.fetchone()
            return (row[0] or "") if row else ""

    def get_user_groups(self, username: str):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT gm.group_name, g.img_b64
                FROM group_members gm  
                LEFT JOIN groups g ON g.name = gm.group_name
                WHERE gm.username=?
                ORDER BY gm.group_name ASC
            """, (username,))
            return [(row[0], row[1] or "") for row in cur.fetchall()]

    def get_group_members(self, group_name: str):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT username FROM group_members WHERE group_name=?", (group_name,))
            return [row[0] for row in cur.fetchall()]

    # =========================================================
    # MESSAGES
    # =========================================================
    def save_message(self, group_name: str, sender: str, content: str) -> int:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO messages(group_name, sender, content) VALUES (?, ?, ?)",
                (group_name, sender, content)
            )
            self.conn.commit()
            return int(cur.lastrowid)

    def get_messages(self, group_name: str, limit: int = 100):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT sender, content, id
                FROM messages
                WHERE group_name=?
                ORDER BY id DESC
                LIMIT ?
            """, (group_name, limit))
            return cur.fetchall()[::-1]

    def get_last_message_id(self, group_name: str) -> int:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT MAX(id) FROM messages WHERE group_name=?", (group_name,))
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0


    # =========================================================
    # FRIENDS
    # =========================================================
    def are_friends(self, user1: str, user2: str) -> bool:
        a, b = self.normalize_friend_pair(user1, user2)
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT 1 FROM friends WHERE user_a=? AND user_b=? LIMIT 1", (a, b))
            return cur.fetchone() is not None

    def send_friend_request(self, from_user: str, to_user: str) -> str:
        if from_user == to_user:
            return "CANT_ADD_SELF"
        if not self.user_exists(to_user):
            return "NO_SUCH_USER"
        if self.are_friends(from_user, to_user):
            return "ALREADY_FRIENDS"

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT 1 FROM friend_requests WHERE from_user=? AND to_user=?",
                (from_user, to_user)
            )
            if cur.fetchone():
                return "ALREADY_SENT"

            try:
                self.conn.execute(
                    "INSERT INTO friend_requests(from_user, to_user) VALUES (?, ?)",
                    (from_user, to_user)
                )
                self.conn.commit()
                return "OK"
            except Exception:
                return "ALREADY_SENT"

    def list_incoming_requests(self, username: str):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT from_user
                FROM friend_requests
                WHERE to_user=?
                ORDER BY ts DESC
            """, (username,))
            return [row[0] for row in cur.fetchall()]

    def accept_friend_request(self, username: str, from_user: str) -> bool:
        if from_user == username:
            return False
        if not self.user_exists(from_user):
            return False

        a, b = self.normalize_friend_pair(username, from_user)

        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT 1 FROM friend_requests WHERE from_user=? AND to_user=?",
                (from_user, username)
            )
            if not cur.fetchone():
                return False

            self.conn.execute(
                "DELETE FROM friend_requests WHERE from_user=? AND to_user=?",
                (from_user, username)
            )
            self.conn.execute(
                "INSERT OR IGNORE INTO friends(user_a, user_b) VALUES (?, ?)",
                (a, b)
            )
            self.conn.commit()
            return True

    def get_friends(self, username: str):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT CASE
                    WHEN user_a=? THEN user_b
                    ELSE user_a
                END AS friend
                FROM friends
                WHERE user_a=? OR user_b=?
                ORDER BY friend ASC
            """, (username, username, username))
            return [row[0] for row in cur.fetchall()]

    # =========================================================
    # READ / UNREAD
    # =========================================================
    def mark_read(self, username: str, group_name: str) -> int:
        last_id = self.get_last_message_id(group_name)
        with self.lock:
            self.conn.execute("""
                INSERT INTO last_read(username, group_name, last_msg_id)
                VALUES(?, ?, ?)
                ON CONFLICT(username, group_name)
                DO UPDATE SET
                    last_msg_id = excluded.last_msg_id,
                    ts = CURRENT_TIMESTAMP
            """, (username, group_name, last_id))
            self.conn.commit()
        return last_id

    def get_unread_count(self, username: str, group_name: str) -> int:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT COALESCE(last_msg_id, 0)
                FROM last_read
                WHERE username=? AND group_name=?
            """, (username, group_name))
            row = cur.fetchone()
            last_read_id = int(row[0]) if row else 0

            cur.execute("""
                SELECT COUNT(*)
                FROM messages
                WHERE group_name=?
                  AND id > ?
                  AND sender <> ?
            """, (group_name, last_read_id, username))
            return int(cur.fetchone()[0])

    def get_unread_all_for_user(self, username: str):
        groups = [group_name for group_name, _img in self.get_user_groups(username)]
        result = {}
        for group_name in groups:
            unread_count = self.get_unread_count(username, group_name)
            if unread_count > 0:
                result[group_name] = unread_count
        return result
