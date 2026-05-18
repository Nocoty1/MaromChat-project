import base64
import hashlib


# Simple shared key for project-level encryption
# This is NOT strong real-world security, but good enough for a school project.
SECRET_KEY = "maromchat_key_2026"


def xor_cipher(text: str, key: str = SECRET_KEY) -> str:
    """
    Simple XOR cipher.
    Used here only for username/password transport in the project.
    """
    if not text:
        return ""

    text_bytes = text.encode()
    key_bytes = key.encode()

    output = bytearray()
    for i, b in enumerate(text_bytes):
        output.append(b ^ key_bytes[i % len(key_bytes)])

    return base64.b64encode(output).decode()


def xor_decipher(encoded_text: str, key: str = SECRET_KEY) -> str:
    """
    Reverse the XOR cipher.
    """
    if not encoded_text:
        return ""

    data = base64.b64decode(encoded_text.encode())
    key_bytes = key.encode()

    output = bytearray()
    for i, b in enumerate(data):
        output.append(b ^ key_bytes[i % len(key_bytes)])

    return output.decode()


def hash_password(password: str) -> str:
    """
    Store passwords as SHA-256 hashes instead of plain text.
    """
    return hashlib.sha256(password.encode()).hexdigest()
