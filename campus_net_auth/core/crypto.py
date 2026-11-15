"""Panabit 门户的账号密码加密（纯 Python AES-128，零依赖）。

认证接口要求 username / password 以十六进制密文提交。等价于页面上的
``pa_aes_encode()``：

    key     = b"Panabit@1024_key"   # 16 字节
    mode    = ECB
    padding = ZeroPadding           # 用 \\x00 补齐到 16 的倍数
    输出    = ciphertext 的小写 hex

不要换成 CBC 或 PKCS7，服务端解不出来只会回一句"用户名不存在"，
很难排查。已用 NIST FIPS-197 测试向量验证，见 ``python -m
campus_net_auth.core.crypto``。
"""

# ---------------------------------------------------------------- S 盒

_SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
]

_INV_SBOX = [0] * 256
for _i, _v in enumerate(_SBOX):
    _INV_SBOX[_v] = _i

_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36,
         0x6c, 0xd8, 0xab, 0x4d, 0x9a, 0x2f]


def _xtime(a):
    a <<= 1
    if a & 0x100:
        a = (a ^ 0x1b) & 0xff
    return a


def _mul(a, b):
    """GF(2^8) 乘法。"""
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        b >>= 1
        a = _xtime(a)
    return p


# ---------------------------------------------------------------- 密钥扩展


def _expand_key(key):
    assert len(key) == 16, "AES-128 需要 16 字节密钥"
    w = [list(key[i * 4:i * 4 + 4]) for i in range(4)]
    for i in range(4, 44):
        t = list(w[i - 1])
        if i % 4 == 0:
            t = t[1:] + t[:1]                       # RotWord
            t = [_SBOX[b] for b in t]               # SubWord
            t[0] ^= _RCON[i // 4 - 1]
        w.append([w[i - 4][j] ^ t[j] for j in range(4)])
    return [sum(w[r * 4:r * 4 + 4], []) for r in range(11)]


# ---------------------------------------------------------------- 轮函数


def _add_round_key(s, k):
    return [s[i] ^ k[i] for i in range(16)]


def _sub_bytes(s, box=_SBOX):
    return [box[b] for b in s]


def _shift_rows(s):
    # 状态按列存放：s[c*4 + r]
    out = [0] * 16
    for c in range(4):
        for r in range(4):
            out[c * 4 + r] = s[((c + r) % 4) * 4 + r]
    return out


def _inv_shift_rows(s):
    out = [0] * 16
    for c in range(4):
        for r in range(4):
            out[c * 4 + r] = s[((c - r) % 4) * 4 + r]
    return out


def _mix_columns(s):
    out = [0] * 16
    for c in range(4):
        a = s[c * 4:c * 4 + 4]
        out[c * 4 + 0] = _mul(a[0], 2) ^ _mul(a[1], 3) ^ a[2] ^ a[3]
        out[c * 4 + 1] = a[0] ^ _mul(a[1], 2) ^ _mul(a[2], 3) ^ a[3]
        out[c * 4 + 2] = a[0] ^ a[1] ^ _mul(a[2], 2) ^ _mul(a[3], 3)
        out[c * 4 + 3] = _mul(a[0], 3) ^ a[1] ^ a[2] ^ _mul(a[3], 2)
    return out


def _inv_mix_columns(s):
    out = [0] * 16
    for c in range(4):
        a = s[c * 4:c * 4 + 4]
        out[c * 4 + 0] = _mul(a[0], 14) ^ _mul(a[1], 11) ^ _mul(a[2], 13) ^ _mul(a[3], 9)
        out[c * 4 + 1] = _mul(a[0], 9) ^ _mul(a[1], 14) ^ _mul(a[2], 11) ^ _mul(a[3], 13)
        out[c * 4 + 2] = _mul(a[0], 13) ^ _mul(a[1], 9) ^ _mul(a[2], 14) ^ _mul(a[3], 11)
        out[c * 4 + 3] = _mul(a[0], 11) ^ _mul(a[1], 13) ^ _mul(a[2], 9) ^ _mul(a[3], 14)
    return out


def _encrypt_block(block, rk):
    s = _add_round_key(list(block), rk[0])
    for rnd in range(1, 10):
        s = _sub_bytes(s)
        s = _shift_rows(s)
        s = _mix_columns(s)
        s = _add_round_key(s, rk[rnd])
    s = _sub_bytes(s)
    s = _shift_rows(s)
    s = _add_round_key(s, rk[10])
    return bytes(s)


def _decrypt_block(block, rk):
    s = _add_round_key(list(block), rk[10])
    for rnd in range(9, 0, -1):
        s = _inv_shift_rows(s)
        s = _sub_bytes(s, _INV_SBOX)
        s = _add_round_key(s, rk[rnd])
        s = _inv_mix_columns(s)
    s = _inv_shift_rows(s)
    s = _sub_bytes(s, _INV_SBOX)
    s = _add_round_key(s, rk[0])
    return bytes(s)


# ---------------------------------------------------------------- 对外接口

DEFAULT_KEY = b"Panabit@1024_key"


def _zero_pad(data):
    if len(data) % 16:
        data += b"\x00" * (16 - len(data) % 16)
    return data


def encrypt_hex(text, key=DEFAULT_KEY):
    """等价 CryptoJS.AES.encrypt(text, key, {mode:ECB, padding:ZeroPadding}).ciphertext.toString()"""
    rk = _expand_key(key)
    data = _zero_pad(text.encode("utf-8"))
    out = b"".join(_encrypt_block(data[i:i + 16], rk) for i in range(0, len(data), 16))
    return out.hex()


def decrypt_hex(hexstr, key=DEFAULT_KEY):
    """等价 pa_aes_decode"""
    rk = _expand_key(key)
    data = bytes.fromhex(hexstr)
    out = b"".join(_decrypt_block(data[i:i + 16], rk) for i in range(0, len(data), 16))
    return out.rstrip(b"\x00").decode("utf-8", "replace")


if __name__ == "__main__":
    # FIPS-197 附录 B 测试向量
    pt = bytes.fromhex("00112233445566778899aabbccddeeff")
    k = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    rk = _expand_key(k)
    ct = _encrypt_block(pt, rk)
    assert ct.hex() == "69c4e0d86a7b0430d8cdb78070b4c55a", ct.hex()
    assert _decrypt_block(ct, rk) == pt
    print("AES-128 测试向量通过")

    # 往返测试
    for s in ["23031901151", "a", "", "中文密码123", "x" * 16, "y" * 17]:
        e = encrypt_hex(s)
        d = decrypt_hex(e) if s else ""
        assert d == s, (s, e, d)
    print("加解密往返通过")
