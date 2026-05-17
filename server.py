import socket
import selectors
import threading
import queue
from database import Database
from security import xor_decipher


class ChatServer:
    def __init__(self, host="127.0.0.1", port=5555):
        self.db = Database()
        self.running = True

        self.selector = selectors.DefaultSelector()
        self.send_queue = queue.Queue()

        self.clients = {}
        self.clients_lock = threading.Lock()

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((host, port))
        self.server_socket.listen()
        self.server_socket.setblocking(False)

        self.selector.register(self.server_socket, selectors.EVENT_READ, data={"type": "server"})

        print("[SERVER READY]", host, port)
        threading.Thread(target=self.sender_loop, daemon=True).start()

    def queue_send(self, sock, message: str):
        self.send_queue.put((sock, (message + "\n").encode()))

    def sender_loop(self):
        while self.running:
            try:
                sock, payload = self.send_queue.get(timeout=0.5)
                sock.sendall(payload)
            except Exception:
                pass

    def disconnect(self, sock):
        with self.clients_lock:
            self.clients.pop(sock, None)
        try:
            self.selector.unregister(sock)
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass

    def find_socket(self, username: str):
        with self.clients_lock:
            for sock, state in self.clients.items():
                if state.get("username") == username:
                    return sock
        return None

    def push_friend_requests_updated(self, username: str):
        sock = self.find_socket(username)
        if sock:
            self.queue_send(sock, "FRIEND_REQUESTS_UPDATED")

    def push_friends_updated(self, username: str):
        sock = self.find_socket(username)
        if sock:
            self.queue_send(sock, "FRIENDS_UPDATED")

    def broadcast(self, group_name: str, sender: str, text: str):
        members = self.db.get_group_members(group_name)
        with self.clients_lock:
            for sock, state in self.clients.items():
                if state.get("username") in members:
                    self.queue_send(sock, f"[{group_name}] {sender}: {text}")

    def dm_name(self, a: str, b: str):
        return f"dm:{min(a, b)}:{max(a, b)}"

    def handle_auth(self, sock, state, parts):
        if len(parts) < 3:
            self.queue_send(sock, "AUTH_FAIL")
            return

        try:
            user = xor_decipher(parts[1])
            pwd = xor_decipher(parts[2])
        except Exception:
            self.queue_send(sock, "AUTH_FAIL")
            return

        if parts[0] == "REGISTER":
            ok = self.db.register_user(user, pwd)
            self.queue_send(sock, "REG_OK" if ok else "REG_FAIL")

        elif parts[0] == "LOGIN":
            ok = self.db.validate_user(user, pwd)
            self.queue_send(sock, "LOGIN_OK" if ok else "LOGIN_FAIL")
            if ok:
                state["username"] = user
                state["authed"] = True

    def handle_cmd(self, sock, state, message: str):
        cmd = message.split("|", 1)[0]
        user = state["username"]

        # ---------- PROFILE ----------
        if cmd == "GET_MY_PROFILE_IMG":
            img = self.db.get_profile_image(user)
            self.queue_send(sock, f"MY_PROFILE_IMG|{img}")

        elif cmd == "SET_PROFILE_IMG":
            parts = message.split("|", 1)
            img_b64 = parts[1] if len(parts) > 1 else ""
            self.db.set_profile_image(user, img_b64)
            self.queue_send(sock, "PROFILE_IMG_OK")

        # ---------- GROUP IMAGE ----------
        elif cmd == "SET_GROUP_IMG":
            parts = message.split("|", 2)
            if len(parts) < 3:
                return
            group_name = parts[1]
            img_b64 = parts[2]
            self.db.set_group_image(group_name, img_b64)
            self.queue_send(sock, "GROUP_IMG_OK")

        # ---------- MESSAGE ----------
        elif cmd == "MSG":
            parts = message.split("|", 2)
            if len(parts) < 3:
                return
            group_name = parts[1]
            text = parts[2]

            self.db.save_message(group_name, user, text)
            self.broadcast(group_name, user, text)

        # ---------- GROUPS ----------
        elif cmd == "MYGROUPS":
            groups = self.db.get_user_groups(user)
            packed = [f"{g}::{img}" for g, img in groups]
            self.queue_send(sock, "MYGROUPS|" + ",".join(packed))

        # ---------- FRIENDS ----------
        elif cmd == "FRIENDS":
            friends = self.db.get_friends(user)
            packed = [f"{f}::{self.db.get_profile_image(f)}" for f in friends]
            self.queue_send(sock, "FRIENDS|" + ",".join(packed))

        # ---------- HISTORY ----------
        elif cmd == "HISTORY":
            parts = message.split("|", 1)
            if len(parts) < 2:
                return
            group_name = parts[1]

            for sender, content, _, _ in self.db.get_messages(group_name):
                self.queue_send(sock, f"[{group_name}] {sender}: {content}")

        # ---------- CREATE GROUP ----------
        elif cmd == "CREATEGROUP":
            parts = message.split("|", 1)
            if len(parts) < 2:
                return
            group = parts[1]

            if self.db.create_group(group):
                self.db.join_group(group, user)
                self.queue_send(sock, "GROUP_OK")
            else:
                self.queue_send(sock, "GROUP_EXISTS")

        elif cmd == "CREATEGROUP2":
            parts = message.split("|", 2)
            if len(parts) < 3:
                return

            group = parts[1]
            members = parts[2].split(",")

            if self.db.create_group(group):
                self.db.join_group(group, user)
                for m in members:
                    if self.db.are_friends(user, m):
                        self.db.join_group(group, m)
                self.queue_send(sock, "GROUP_OK")
            else:
                self.queue_send(sock, "GROUP_EXISTS")

        # ---------- INVITE ----------
        elif cmd == "INVITE_GROUP":
            parts = message.split("|", 2)
            if len(parts) < 3:
                return

            group = parts[1]
            members = parts[2].split(",")

            for m in members:
                if self.db.are_friends(user, m):
                    self.db.join_group(group, m)

            self.queue_send(sock, "INVITE_OK")

        # ---------- LEAVE ----------
        elif cmd == "LEAVEGROUP":
            parts = message.split("|", 1)
            if len(parts) < 2:
                return

            group = parts[1]
            self.db.leave_group(group, user)
            self.queue_send(sock, "LEAVE_OK")

        # ---------- DM ----------
        elif cmd == "DM_OPEN":
            parts = message.split("|", 1)
            if len(parts) < 2:
                return

            friend = parts[1]
            if not self.db.are_friends(user, friend):
                return

            group = self.dm_name(user, friend)
            self.db.ensure_group(group)
            self.db.join_group(group, user)
            self.db.join_group(group, friend)

            self.queue_send(sock, f"DM_OK|{group}|{friend}")

        # ---------- SEARCH ----------
        elif cmd == "SEARCH_USER":
            parts = message.split("|", 1)
            query = parts[1] if len(parts) > 1 else ""

            if self.db.user_exists(query):
                self.queue_send(sock, f"SEARCH_RESULT|{query}")
            else:
                self.queue_send(sock, "SEARCH_RESULT|")

        # ---------- FRIEND REQUEST ----------
        elif cmd == "FRIEND_REQUEST":
            parts = message.split("|", 1)
            if len(parts) < 2:
                return

            to_user = parts[1].strip()

            result = self.db.send_friend_request(user, to_user)
            self.queue_send(sock, f"FRIEND_REQUEST_RESULT|{result}")

            if result == "OK":
                self.push_friend_requests_updated(to_user)


        elif cmd == "FRIEND_REQUESTS":
            requests = self.db.list_incoming_requests(user)
            self.queue_send(sock, "FRIEND_REQUESTS|" + ",".join(requests))


        elif cmd == "FRIEND_ACCEPT":
            parts = message.split("|", 1)
            if len(parts) < 2:
                return

            from_user = parts[1].strip()

            ok = self.db.accept_friend_request(user, from_user)

            if ok:
                self.queue_send(sock, "FRIEND_ACCEPT_OK")

                self.push_friend_requests_updated(user)
                self.push_friends_updated(user)
                self.push_friends_updated(from_user)
            else:
                self.queue_send(sock, "FRIEND_ACCEPT_FAIL")

        # ---------- READ ----------
        elif cmd == "MARK_READ":
            parts = message.split("|", 1)
            group = parts[1]

            self.db.mark_read(user, group)
            self.queue_send(sock, "MARK_READ_OK")

        elif cmd == "UNREAD_ALL":
            unread = self.db.get_unread_all_for_user(user)
            packed = ",".join([f"{k}={v}" for k, v in unread.items()])
            self.queue_send(sock, "UNREAD_ALL|" + packed)

    def start(self):
        while self.running:
            for key, _ in self.selector.select(0.5):
                if key.data["type"] == "server":
                    sock, addr = self.server_socket.accept()
                    sock.setblocking(False)
                    state = {"type": "client", "buffer": b"", "authed": False, "username": ""}
                    with self.clients_lock:
                        self.clients[sock] = state
                    self.selector.register(sock, selectors.EVENT_READ, data=state)

                else:
                    sock = key.fileobj
                    state = key.data

                    try:
                        data = sock.recv(65536)
                        if not data:
                            self.disconnect(sock)
                            continue

                        state["buffer"] += data

                        while b"\n" in state["buffer"]:
                            line, state["buffer"] = state["buffer"].split(b"\n", 1)
                            if not line:
                                continue

                            message = line.decode(errors="ignore")

                            if not state["authed"]:
                                parts = message.split("|", 2)
                                self.handle_auth(sock, state, parts)
                            else:
                                self.handle_cmd(sock, state, message)

                    except Exception:
                        self.disconnect(sock)


if __name__ == "__main__":
    ChatServer().start()
