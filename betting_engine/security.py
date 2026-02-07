import base64
from django.conf import settings

def _get_key():
    val = getattr(settings, 'SECRET_KEY', 'django-insecure-default-key-should-be-changed')
    return val if val else 'fallback-key'

def xor_cipher(text, key):
    # Simple XOR cipher
    return ''.join(chr(ord(c) ^ ord(k)) for c, k in zip(text, key * (len(text) // len(key) + 1)))

def encrypt_credential(plaintext):
    """
    Encrypts plaintext using simple XOR + Base64.
    Prefixes with 'ENC::' to identify encrypted data.
    """
    if not plaintext:
        return ""
    if plaintext.startswith("ENC::"):
        return plaintext
        
    key = _get_key()
    # XOR
    xored = xor_cipher(plaintext, key)
    # Base64 Encode to make it safe for DB storage
    encoded = base64.b64encode(xored.encode('utf-8')).decode('utf-8')
    return f"ENC::{encoded}"

def decrypt_credential(ciphertext):
    """
    Decrypts ciphertext. Returns original if not encrypted.
    """
    if not ciphertext or not ciphertext.startswith("ENC::"):
        return ciphertext
        
    try:
        key = _get_key()
        encoded = ciphertext[5:]
        # Base64 Decode
        xored = base64.b64decode(encoded).decode('utf-8')
        # XOR (Reversible)
        return xor_cipher(xored, key)
    except Exception as e:
        print(f"Decryption error: {e}")
        return ""
