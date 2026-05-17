import socket
import threading
from security import xor_cipher


class MaromChatClient:
    def __init__(self, gui, host="127.0.0.1", port=5555):
        self.gui = gui
        self.sock = socket.socket()
        self.sock.connect((host, port))
        self.buffer = b""

        threading.Thread(target=self.listen, daemon=True).start()

    def send(self, msg: str):
        self.sock.sendall((msg + "\n").encode())

    def login(self, username: str, password: str):
        self.send(f"LOGIN|{xor_cipher(username)}|{xor_cipher(password)}")

    def register(self, username: str, password: str):
        self.send(f"REGISTER|{xor_cipher(username)}|{xor_cipher(password)}")

    def set_profile_image(self, img_b64: str):
        self.send(f"SET_PROFILE_IMG|{img_b64}")

    def get_my_profile_image(self):
        self.send("GET_MY_PROFILE_IMG|")

    def set_group_image(self, group_name: str, img_b64: str):
        self.send(f"SET_GROUP_IMG|{group_name}|{img_b64}")

    def send_message(self, group_name: str, text: str):
        text = text.replace("\n", " ")
        self.send(f"MSG|{group_name}|{text}")

    def my_groups(self):
        self.send("MYGROUPS|")

    def get_friends(self):
        self.send("FRIENDS|")

    def unread_all(self):
        self.send("UNREAD_ALL|")

    def load_history(self, group_name: str):
        self.send(f"HISTORY|{group_name}")

    def mark_read(self, group_name: str):
        self.send(f"MARK_READ|{group_name}")

    def open_dm(self, username: str):
        self.send(f"DM_OPEN|{username}")

    def create_group(self, group_name: str):
        self.send(f"CREATEGROUP|{group_name}")

    def create_group_with_friends(self, group_name: str, members: list[str]):
        self.send(f"CREATEGROUP2|{group_name}|{','.join(members)}")

    def join_group(self, group_name: str):
        self.send(f"JOINGROUP|{group_name}")

    def leave_group(self, group_name: str):
        self.send(f"LEAVEGROUP|{group_name}")

    def invite_group(self, group_name: str, members: list[str]):
        self.send(f"INVITE_GROUP|{group_name}|{','.join(members)}")

    def search_user(self, query: str):
        self.send(f"SEARCH_USER|{query}")

    def send_friend_request(self, username: str):
        self.send(f"FRIEND_REQUEST|{username}")

    def get_friend_requests(self):
        self.send("FRIEND_REQUESTS|")

    def accept_friend(self, username: str):
        self.send(f"FRIEND_ACCEPT|{username}")

    def listen(self):
        while True:
            try:
                data = self.sock.recv(65536)
                if not data:
                    break

                self.buffer += data

                while b"\n" in self.buffer:
                    line, self.buffer = self.buffer.split(b"\n", 1)
                    if line:
                        message = line.decode(errors="ignore")

                        # חשוב: עדכון GUI חייב להיות דרך main thread
                        self.gui.root.after(0, self.gui.receive_message, message)

            except Exception:
                break
