"""Real symmetric crypto primitives (stdlib only, pure Python).

Provides actual decryption — not simulated — for preservation
workflows where the operator supplies key material they lawfully
possess (device backup export, vendor tooling, archival notes):

  - AES-128 / AES-192 / AES-256, ECB + CBC, PKCS#7 unpad
  - XOR stream (repeating key)
  - SHA-256 key-derivation helper (single-round, transparent)
  - Zip Traditional / AES entries via caller-supplied password

No hard-coded Microsoft keys. No key database. No brute force.
Keys arrive from CLI args / GUI fields at runtime only and are
never written to the catalog DB.
"""
from __future__ import annotations

import hashlib


# ---------------------------------------------------------------- AES ---

_SBOX = (
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
)
_INV_SBOX = [0] * 256
for _i, _v in enumerate(_SBOX):
    _INV_SBOX[_v] = _i

_RCON = (0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36)


def _xtime(a: int) -> int:
    return ((a << 1) ^ 0x1b) & 0xff if a & 0x80 else (a << 1) & 0xff


def _gmul(a: int, b: int) -> int:
    r = 0
    while b:
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r & 0xff


def _expand_key(key: bytes) -> list[list[int]]:
    nk = len(key) // 4
    nr = {4: 10, 6: 12, 8: 14}[nk]
    nb = 4
    w: list[list[int]] = []
    for i in range(nk):
        w.append([key[4*i], key[4*i+1], key[4*i+2], key[4*i+3]])
    for i in range(nk, nb * (nr + 1)):
        temp = w[i-1][:]
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [_SBOX[b] for b in temp]
            temp[0] ^= _RCON[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            temp = [_SBOX[b] for b in temp]
        w.append([w[i-nk][j] ^ temp[j] for j in range(4)])
    rounds = []
    for r in range(nr + 1):
        rk = []
        for c in range(4):
            rk += w[r*4 + c]
        rounds.append(rk)
    return rounds


def _add_round_key(s: list[int], rk: list[int]) -> list[int]:
    return [s[i] ^ rk[i] for i in range(16)]


def _sub_bytes(s: list[int], inv: bool = False) -> list[int]:
    box = _INV_SBOX if inv else _SBOX
    return [box[b] for b in s]


def _shift_rows(s: list[int], inv: bool = False) -> list[int]:
    # state is column-major: s[row + 4*col]
    out = [0] * 16
    for r in range(4):
        for c in range(4):
            if not inv:
                out[r + 4*c] = s[r + 4*((c + r) % 4)]
            else:
                out[r + 4*c] = s[r + 4*((c - r) % 4)]
    return out


def _mix_columns(s: list[int], inv: bool = False) -> list[int]:
    out = [0] * 16
    for c in range(4):
        a = s[c*4:(c+1)*4]
        if not inv:
            out[c*4+0] = _gmul(a[0],2) ^ _gmul(a[1],3) ^ a[2] ^ a[3]
            out[c*4+1] = a[0] ^ _gmul(a[1],2) ^ _gmul(a[2],3) ^ a[3]
            out[c*4+2] = a[0] ^ a[1] ^ _gmul(a[2],2) ^ _gmul(a[3],3)
            out[c*4+3] = _gmul(a[0],3) ^ a[1] ^ a[2] ^ _gmul(a[3],2)
        else:
            out[c*4+0] = _gmul(a[0],14) ^ _gmul(a[1],11) ^ _gmul(a[2],13) ^ _gmul(a[3],9)
            out[c*4+1] = _gmul(a[0],9) ^ _gmul(a[1],14) ^ _gmul(a[2],11) ^ _gmul(a[3],13)
            out[c*4+2] = _gmul(a[0],13) ^ _gmul(a[1],9) ^ _gmul(a[2],14) ^ _gmul(a[3],11)
            out[c*4+3] = _gmul(a[0],11) ^ _gmul(a[1],13) ^ _gmul(a[2],9) ^ _gmul(a[3],14)
    return out


def _enc_block(block: bytes, round_keys: list[list[int]]) -> bytes:
    s = list(block)
    s = _add_round_key(s, round_keys[0])
    for rk in round_keys[1:-1]:
        s = _sub_bytes(s)
        s = _shift_rows(s)
        s = _mix_columns(s)
        s = _add_round_key(s, rk)
    s = _sub_bytes(s)
    s = _shift_rows(s)
    s = _add_round_key(s, round_keys[-1])
    return bytes(s)


def _dec_block(block: bytes, round_keys: list[list[int]]) -> bytes:
    s = list(block)
    s = _add_round_key(s, round_keys[-1])
    for rk in reversed(round_keys[1:-1]):
        s = _shift_rows(s, inv=True)
        s = _sub_bytes(s, inv=True)
        s = _add_round_key(s, rk)
        s = _mix_columns(s, inv=True)
    s = _shift_rows(s, inv=True)
    s = _sub_bytes(s, inv=True)
    s = _add_round_key(s, round_keys[0])
    return bytes(s)


def aes_ecb_encrypt(data: bytes, key: bytes) -> bytes:
    if len(key) not in (16, 24, 32):
        raise ValueError("AES key must be 16/24/32 bytes")
    if len(data) % 16:
        raise ValueError("ECB input must be a multiple of 16 bytes")
    rk = _expand_key(key)
    return b"".join(_enc_block(data[i:i+16], rk) for i in range(0, len(data), 16))


def aes_ecb_decrypt(data: bytes, key: bytes) -> bytes:
    if len(key) not in (16, 24, 32):
        raise ValueError("AES key must be 16/24/32 bytes")
    if len(data) % 16 or not data:
        raise ValueError("ECB input must be a non-empty multiple of 16 bytes")
    rk = _expand_key(key)
    return b"".join(_dec_block(data[i:i+16], rk) for i in range(0, len(data), 16))


def aes_cbc_decrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    if len(iv) != 16:
        raise ValueError("IV must be 16 bytes")
    raw = aes_ecb_decrypt(data, key)
    out = bytearray()
    prev = iv
    for i in range(0, len(raw), 16):
        blk = raw[i:i+16]
        out += bytes(blk[j] ^ prev[j] for j in range(16))
        prev = data[i:i+16]
    return bytes(out)


def aes_cbc_encrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    if len(iv) != 16:
        raise ValueError("IV must be 16 bytes")
    if len(data) % 16:
        raise ValueError("CBC input must be a multiple of 16 bytes")
    rk = _expand_key(key)
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        blk = bytes(data[i+j] ^ prev[j] for j in range(16))
        enc = _enc_block(blk, rk)
        out += enc
        prev = enc
    return bytes(out)


def aes_ctr_crypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-CTR (symmetric — encrypt == decrypt). PlayReady AESCTR path.

    16-byte IV/counter, big-endian increment per 16-byte block, final
    partial block truncated. Operator supplies key + IV; nothing stored.
    """
    if len(key) not in (16, 24, 32):
        raise ValueError("AES key must be 16/24/32 bytes")
    if len(iv) != 16:
        raise ValueError("IV must be 16 bytes")
    rk = _expand_key(key)
    out = bytearray()
    ctr = int.from_bytes(iv, "big")
    for i in range(0, len(data), 16):
        keystream = _enc_block(ctr.to_bytes(16, "big"), rk)
        blk = data[i:i + 16]
        out += bytes(blk[j] ^ keystream[j] for j in range(len(blk)))
        ctr = (ctr + 1) & ((1 << 128) - 1)
    return bytes(out)


def pkcs7_pad(data: bytes, block: int = 16) -> bytes:
    n = block - (len(data) % block)
    return data + bytes([n]) * n


def pkcs7_unpad(data: bytes, block: int = 16) -> bytes:
    if not data or len(data) % block:
        raise ValueError("bad PKCS#7 length")
    n = data[-1]
    if n < 1 or n > block or data[-n:] != bytes([n]) * n:
        raise ValueError("bad PKCS#7 padding")
    return data[:-n]


def xor_stream(data: bytes, key: bytes) -> bytes:
    if not key:
        raise ValueError("XOR key must be non-empty")
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def derive_key_sha256(password: bytes, salt: bytes = b"comz-preservation-v1",
                      length: int = 32, iterations: int = 1) -> bytes:
    """Transparent single-purpose KDF: SHA-256(password|salt) iterated.

    Documented so archival notes can reproduce the transform exactly.
    Not a password-cracking helper — derives a file key from operator
    notes they already hold for a copy they already own.
    """
    if length not in (16, 24, 32):
        raise ValueError("derived length must be 16/24/32")
    acc = password + salt
    for _ in range(max(1, iterations)):
        acc = hashlib.sha256(acc).digest()
    while len(acc) < length:
        acc += hashlib.sha256(acc).digest()
    return acc[:length]


def parse_key_hex(s: str) -> bytes:
    s = s.strip().lower().replace("0x", "").replace(" ", "").replace("-", "")
    if len(s) % 2 or not s:
        raise ValueError("key-hex must be even-length hex")
    try:
        k = bytes.fromhex(s)
    except ValueError:
        raise ValueError("key-hex is not valid hex")
    if len(k) not in (16, 24, 32):
        raise ValueError("key must decode to 16/24/32 bytes (AES-128/192/256)")
    return k
