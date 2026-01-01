#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ofuscador/Desofuscador avançado – 11 técnicas originais + 8 criptografias reais
Use apenas em código que você tem permissão para modificar.
"""

import os
import base64
import zlib
import marshal
import codecs
import random
import lzma
import sys
import re

# ============================================================================
# UTILIDADES DE CONSOLE
# ============================================================================

def clear_console():
    os.system("cls" if os.name == "nt" else "clear")

def linha(tam=60, ch="="):
    print(ch * tam)

# ============================================================================
# Tentativa de importar bibliotecas de criptografia
# ============================================================================

HAVE_CRYPTO = False
HAVE_CRYPTOGRAPHY = False

try:
    from Crypto.Cipher import AES, Blowfish, DES3, ChaCha20, Salsa20, ARC4
    from Crypto.Random import get_random_bytes
    HAVE_CRYPTO = True
except Exception:
    pass

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    HAVE_CRYPTOGRAPHY = True
except Exception:
    pass

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

pasta_combo = "/sdcard/combo/"

clear_console()
linha()
print("🔐 OFUSCADOR PYTHON AVANÇADO")
print("   11 Técnicas + 8 Criptografias Reais")
linha()

if not os.path.isdir(pasta_combo):
    print(f"⚠️ Pasta '{pasta_combo}' não encontrada. Usando diretório atual.")
    pasta_combo = "."

# ============================================================================
# LISTAR ARQUIVOS
# ============================================================================

arquivos = [f for f in os.listdir(pasta_combo) if f.endswith(".py")]

if not arquivos:
    print("❌ Nenhum arquivo .py encontrado.")
    sys.exit(0)

print("\n📂 Arquivos disponíveis:\n")
for idx, nome in enumerate(arquivos, 1):
    print(f"  [{idx}] {nome}")

linha()

try:
    escolha = int(input("👉 Escolha o número do arquivo: ")) - 1
    assert 0 <= escolha < len(arquivos)
except Exception:
    print("❌ Escolha inválida.")
    sys.exit(0)

arquivo_escolhido = arquivos[escolha]
caminho = os.path.join(pasta_combo, arquivo_escolhido)

clear_console()
linha()
print(f"📄 Sua escolha: {arquivo_escolhido}")
linha()

with open(caminho, "r", encoding="utf-8", errors="replace") as f:
    conteudo_original = f.read()

# ============================================================================
# FERRAMENTAS AUXILIARES
# ============================================================================

def sanitize_filename(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)

def pad_pkcs7(data, block=16):
    pad_len = block - (len(data) % block)
    return data + bytes([pad_len]) * pad_len

def gen_junk_code(n_funcs=4, max_lines=5):
    junk = ""
    for _ in range(n_funcs):
        fname = f"_junk_{random.randint(1000,9999)}"
        junk += f"def {fname}():\n"
        for _ in range(random.randint(1, max_lines)):
            junk += f"    _v = {random.randint(1,9999)}\n"
        junk += "    return None\n\n"
    return junk

# ============================================================================
# TÉCNICAS ORIGINAIS DE OFUSCAÇÃO (1-11)
# ============================================================================

def ofuscar_base64_zlib_marshal(codigo):
    c = marshal.dumps(compile(codigo, "<x>", "exec"))
    c = zlib.compress(c)
    c = base64.b64encode(c).decode()
    return f"""
import base64,zlib,marshal
exec(marshal.loads(zlib.decompress(base64.b64decode(b'{c}'))))
"""

def ofuscar_rot13_hex(codigo):
    rot = codecs.encode(codigo, "rot_13")
    hx = rot.encode().hex()
    return f"""
import codecs
exec(codecs.decode(bytes.fromhex('{hx}').decode(),'rot_13'))
"""

def ofuscar_base85(codigo):
    c = zlib.compress(codigo.encode())
    c = base64.b85encode(c).decode()
    return f"""
import base64,zlib
exec(zlib.decompress(base64.b85decode('{c}')).decode())
"""

def ofuscar_xor_base64(codigo):
    key = random.randint(1,255)
    data = bytes([b ^ key for b in codigo.encode()])
    b64 = base64.b64encode(data).decode()
    return f"""
import base64
key={key}
d=base64.b64decode('{b64}')
exec(bytes([x ^ key for x in d]).decode())
"""

def ofuscar_triple_layer(codigo):
    c1 = marshal.dumps(compile(codigo,"<x>","exec"))
    c2 = zlib.compress(c1)
    c3 = base64.b64encode(c2)
    final = marshal.dumps(c3)
    return f"""
import marshal,base64,zlib
c=marshal.loads({final})
d=base64.b64decode(c)
d=zlib.decompress(d)
exec(marshal.loads(d))
"""

def ofuscar_multilayer_heavy(codigo):
    c1 = marshal.dumps(compile(codigo,"<x>","exec"))
    c2 = base64.b64encode(c1)
    c3 = base64.b85encode(c2)
    hx = c3.hex()
    return f"""
import base64,marshal
b=bytes.fromhex('{hx}')
b=base64.b85decode(b)
b=base64.b64decode(b)
exec(marshal.loads(b))
"""

def ofuscar_aes_cbc(codigo):
    """AES-128 CBC - Criptografia simétrica padrão"""
    if not HAVE_CRYPTO:
        raise RuntimeError("PyCryptodome não instalado: pip install pycryptodome")
    payload = zlib.compress(codigo.encode())
    key = get_random_bytes(16)
    iv = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ct = cipher.encrypt(pad_pkcs7(payload))
    final = base64.b64encode(iv+ct).decode()
    k = base64.b64encode(key).decode()
    return f"""
import base64,zlib
from Crypto.Cipher import AES
k=base64.b64decode('{k}')
p=base64.b64decode('{final}')
iv=p[:16]; ct=p[16:]
c=AES.new(k,AES.MODE_CBC,iv)
d=c.decrypt(ct)
d=d[:-d[-1]]
exec(zlib.decompress(d).decode())
"""

def ofuscar_lzma_base64(codigo):
    comp = lzma.compress(codigo.encode())
    b64 = base64.b64encode(comp).decode()
    return f"""
import base64,lzma
exec(lzma.decompress(base64.b64decode('{b64}')).decode())
"""

def ofuscar_with_junk(codigo):
    junk = gen_junk_code()
    merged = junk + codigo
    comp = zlib.compress(merged.encode())
    b64 = base64.b64encode(comp).decode()
    return f"""
import base64,zlib
exec(zlib.decompress(base64.b64decode('{b64}')).decode())
"""

def ofuscar_reverse_b64_zlib_marshal(codigo):
    compiled = compile(codigo, "<rev>", "exec")
    dumped = marshal.dumps(compiled)
    compressed = zlib.compress(dumped, 9)
    encoded = base64.b64encode(compressed)
    reversed_payload = encoded[::-1].decode()
    return f"""
_ = lambda __ : __import__('marshal').loads(
    __import__('zlib').decompress(
        __import__('base64').b64decode(__[::-1])
    )
)
exec((_)(b'{reversed_payload}'))
"""

def ofuscar_misturador_aleatorio(codigo):
    tecnicas = [
        ofuscar_base64_zlib_marshal,
        ofuscar_rot13_hex,
        ofuscar_base85,
        ofuscar_xor_base64,
        ofuscar_triple_layer,
        ofuscar_multilayer_heavy,
        ofuscar_lzma_base64,
        ofuscar_with_junk,
        ofuscar_reverse_b64_zlib_marshal,
    ]
    if HAVE_CRYPTO:
        tecnicas.append(ofuscar_aes_cbc)
    return random.choice(tecnicas)(codigo)

# ============================================================================
# CRIPTOGRAFIAS REAIS (12-19)
# ============================================================================

def ofuscar_aes_256_gcm(codigo):
    """AES-256 GCM - Criptografia autenticada com verificação de integridade"""
    if not HAVE_CRYPTO:
        raise RuntimeError("PyCryptodome não instalado: pip install pycryptodome")
    payload = zlib.compress(codigo.encode())
    key = get_random_bytes(32)  # 256 bits
    nonce = get_random_bytes(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ct, tag = cipher.encrypt_and_digest(payload)
    final = base64.b64encode(nonce + tag + ct).decode()
    k = base64.b64encode(key).decode()
    return f"""
import base64,zlib
from Crypto.Cipher import AES
k=base64.b64decode('{k}')
p=base64.b64decode('{final}')
nonce=p[:12]; tag=p[12:28]; ct=p[28:]
c=AES.new(k,AES.MODE_GCM,nonce=nonce)
d=c.decrypt_and_verify(ct,tag)
exec(zlib.decompress(d).decode())
"""

def ofuscar_aes_ctr(codigo):
    """AES-128 CTR - Modo contador, sem necessidade de padding"""
    if not HAVE_CRYPTO:
        raise RuntimeError("PyCryptodome não instalado: pip install pycryptodome")
    payload = zlib.compress(codigo.encode())
    key = get_random_bytes(16)
    nonce = get_random_bytes(8)
    cipher = AES.new(key, AES.MODE_CTR, nonce=nonce)
    ct = cipher.encrypt(payload)
    final = base64.b64encode(nonce + ct).decode()
    k = base64.b64encode(key).decode()
    return f"""
import base64,zlib
from Crypto.Cipher import AES
k=base64.b64decode('{k}')
p=base64.b64decode('{final}')
nonce=p[:8]; ct=p[8:]
c=AES.new(k,AES.MODE_CTR,nonce=nonce)
d=c.decrypt(ct)
exec(zlib.decompress(d).decode())
"""

def ofuscar_blowfish(codigo):
    """Blowfish CBC - Algoritmo clássico de criptografia simétrica"""
    if not HAVE_CRYPTO:
        raise RuntimeError("PyCryptodome não instalado: pip install pycryptodome")
    payload = zlib.compress(codigo.encode())
    key = get_random_bytes(16)
    iv = get_random_bytes(8)
    cipher = Blowfish.new(key, Blowfish.MODE_CBC, iv)
    padded = pad_pkcs7(payload, 8)
    ct = cipher.encrypt(padded)
    final = base64.b64encode(iv + ct).decode()
    k = base64.b64encode(key).decode()
    return f"""
import base64,zlib
from Crypto.Cipher import Blowfish
k=base64.b64decode('{k}')
p=base64.b64decode('{final}')
iv=p[:8]; ct=p[8:]
c=Blowfish.new(k,Blowfish.MODE_CBC,iv)
d=c.decrypt(ct)
d=d[:-d[-1]]
exec(zlib.decompress(d).decode())
"""

def ofuscar_triple_des(codigo):
    """Triple DES (3DES) - Criptografia legada mas ainda segura"""
    if not HAVE_CRYPTO:
        raise RuntimeError("PyCryptodome não instalado: pip install pycryptodome")
    payload = zlib.compress(codigo.encode())
    key = get_random_bytes(24)  # 192 bits para 3DES
    iv = get_random_bytes(8)
    cipher = DES3.new(key, DES3.MODE_CBC, iv)
    padded = pad_pkcs7(payload, 8)
    ct = cipher.encrypt(padded)
    final = base64.b64encode(iv + ct).decode()
    k = base64.b64encode(key).decode()
    return f"""
import base64,zlib
from Crypto.Cipher import DES3
k=base64.b64decode('{k}')
p=base64.b64decode('{final}')
iv=p[:8]; ct=p[8:]
c=DES3.new(k,DES3.MODE_CBC,iv)
d=c.decrypt(ct)
d=d[:-d[-1]]
exec(zlib.decompress(d).decode())
"""

def ofuscar_chacha20(codigo):
    """ChaCha20 - Criptografia de stream moderna e rápida"""
    if not HAVE_CRYPTO:
        raise RuntimeError("PyCryptodome não instalado: pip install pycryptodome")
    payload = zlib.compress(codigo.encode())
    key = get_random_bytes(32)
    nonce = get_random_bytes(8)
    cipher = ChaCha20.new(key=key, nonce=nonce)
    ct = cipher.encrypt(payload)
    final = base64.b64encode(nonce + ct).decode()
    k = base64.b64encode(key).decode()
    return f"""
import base64,zlib
from Crypto.Cipher import ChaCha20
k=base64.b64decode('{k}')
p=base64.b64decode('{final}')
nonce=p[:8]; ct=p[8:]
c=ChaCha20.new(key=k,nonce=nonce)
d=c.decrypt(ct)
exec(zlib.decompress(d).decode())
"""

def ofuscar_salsa20(codigo):
    """Salsa20 - Stream cipher de alta performance"""
    if not HAVE_CRYPTO:
        raise RuntimeError("PyCryptodome não instalado: pip install pycryptodome")
    payload = zlib.compress(codigo.encode())
    key = get_random_bytes(32)
    nonce = get_random_bytes(8)
    cipher = Salsa20.new(key=key, nonce=nonce)
    ct = cipher.encrypt(payload)
    final = base64.b64encode(nonce + ct).decode()
    k = base64.b64encode(key).decode()
    return f"""
import base64,zlib
from Crypto.Cipher import Salsa20
k=base64.b64decode('{k}')
p=base64.b64decode('{final}')
nonce=p[:8]; ct=p[8:]
c=Salsa20.new(key=k,nonce=nonce)
d=c.decrypt(ct)
exec(zlib.decompress(d).decode())
"""

def ofuscar_rc4(codigo):
    """RC4/ARC4 - Stream cipher clássico"""
    if not HAVE_CRYPTO:
        raise RuntimeError("PyCryptodome não instalado: pip install pycryptodome")
    payload = zlib.compress(codigo.encode())
    key = get_random_bytes(16)
    cipher = ARC4.new(key)
    ct = cipher.encrypt(payload)
    final = base64.b64encode(ct).decode()
    k = base64.b64encode(key).decode()
    return f"""
import base64,zlib
from Crypto.Cipher import ARC4
k=base64.b64decode('{k}')
p=base64.b64decode('{final}')
c=ARC4.new(k)
d=c.decrypt(p)
exec(zlib.decompress(d).decode())
"""

def ofuscar_fernet(codigo):
    """Fernet - Criptografia simétrica com verificação de integridade"""
    if not HAVE_CRYPTOGRAPHY:
        raise RuntimeError("cryptography não instalado: pip install cryptography")
    payload = zlib.compress(codigo.encode())
    key = Fernet.generate_key()
    f = Fernet(key)
    ct = f.encrypt(payload)
    final = base64.b64encode(ct).decode()
    k = key.decode()
    return f"""
import base64,zlib
from cryptography.fernet import Fernet
k=b'{k}'
p=base64.b64decode('{final}')
f=Fernet(k)
d=f.decrypt(p)
exec(zlib.decompress(d).decode())
"""

# ============================================================================
# MENU (COM ESCALAS)
# ============================================================================

linha()
print("🎯 Escolha uma técnica de ofuscação (Escala 1–10):\n")
print("""
╔════════════════════════════════════════════════════════════╗
║              TÉCNICAS ORIGINAIS (1-11)                     ║
╠════════════════════════════════════════════════════════════╣
║  1  = Base64 + Zlib + Marshal        [4/10]                ║
║  2  = ROT13 + HEX                    [1/10]                ║
║  3  = Base85 + Zlib                  [3/10]                ║
║  4  = XOR + Base64                   [4/10]                ║
║  5  = Triple Layer                   [7/10]                ║
║  6  = Multilayer Heavy               [8/10]                ║
║  7  = AES-128 CBC + Base64           [9/10]  🔒            ║
║  8  = LZMA + Base64                  [5/10]                ║
║  9  = Junk Code + Compress           [6/10]                ║
║ 10  = Misturador Aleatório           [8/10]                ║
║ 11  = Reverse + B64 + Zlib + Marshal [7/10]                ║
╠════════════════════════════════════════════════════════════╣
║           CRIPTOGRAFIAS REAIS (12-19)                      ║
╠════════════════════════════════════════════════════════════╣
║ 12  = AES-256 GCM (autenticado)      [10/10] 🔒            ║
║ 13  = AES-128 CTR (contador)         [9/10]  🔒            ║
║ 14  = Blowfish CBC                   [8/10]  🔒            ║
║ 15  = Triple DES (3DES)              [7/10]  🔒            ║
║ 16  = ChaCha20 (stream)              [9/10]  🔒            ║
║ 17  = Salsa20 (stream)               [9/10]  🔒            ║
║ 18  = RC4/ARC4 (stream)              [5/10]  🔒            ║
║ 19  = Fernet (cryptography)          [9/10]  🔒            ║
╠════════════════════════════════════════════════════════════╣
║  0  = TURBO MÁXIMO (todas camadas)   [10/10] 🚀🔒          ║
╚════════════════════════════════════════════════════════════╝
""")

if not HAVE_CRYPTO:
    print("⚠️  PyCryptodome não instalado. Técnicas 7, 12-18 indisponíveis.")
    print("    Instale com: pip install pycryptodome")
if not HAVE_CRYPTOGRAPHY:
    print("⚠️  cryptography não instalado. Técnica 19 indisponível.")
    print("    Instale com: pip install cryptography")

linha()

tecnica = input("👉 Técnica escolhida: ").strip()

# ============================================================================
# PROCESSAMENTO
# ============================================================================

try:
    if tecnica == "1":   res = ofuscar_base64_zlib_marshal(conteudo_original)
    elif tecnica == "2": res = ofuscar_rot13_hex(conteudo_original)
    elif tecnica == "3": res = ofuscar_base85(conteudo_original)
    elif tecnica == "4": res = ofuscar_xor_base64(conteudo_original)
    elif tecnica == "5": res = ofuscar_triple_layer(conteudo_original)
    elif tecnica == "6": res = ofuscar_multilayer_heavy(conteudo_original)
    elif tecnica == "7": res = ofuscar_aes_cbc(conteudo_original)
    elif tecnica == "8": res = ofuscar_lzma_base64(conteudo_original)
    elif tecnica == "9": res = ofuscar_with_junk(conteudo_original)
    elif tecnica == "10": res = ofuscar_misturador_aleatorio(conteudo_original)
    elif tecnica == "11": res = ofuscar_reverse_b64_zlib_marshal(conteudo_original)
    # Criptografias reais
    elif tecnica == "12": res = ofuscar_aes_256_gcm(conteudo_original)
    elif tecnica == "13": res = ofuscar_aes_ctr(conteudo_original)
    elif tecnica == "14": res = ofuscar_blowfish(conteudo_original)
    elif tecnica == "15": res = ofuscar_triple_des(conteudo_original)
    elif tecnica == "16": res = ofuscar_chacha20(conteudo_original)
    elif tecnica == "17": res = ofuscar_salsa20(conteudo_original)
    elif tecnica == "18": res = ofuscar_rc4(conteudo_original)
    elif tecnica == "19": res = ofuscar_fernet(conteudo_original)
    elif tecnica == "0":
        # TURBO: aplica múltiplas camadas incluindo criptografias reais
        seq = [
            ofuscar_with_junk,
            ofuscar_lzma_base64,
            ofuscar_xor_base64,
            ofuscar_base85,
            ofuscar_multilayer_heavy,
            ofuscar_triple_layer,
            ofuscar_reverse_b64_zlib_marshal,
        ]
        out = conteudo_original
        for fn in seq:
            out = fn(out)
        # Adiciona camadas de criptografia real se disponível
        if HAVE_CRYPTO:
            out = ofuscar_chacha20(out)
            out = ofuscar_aes_256_gcm(out)
        if HAVE_CRYPTOGRAPHY:
            out = ofuscar_fernet(out)
        res = out
    else:
        print("❌ Técnica inválida.")
        sys.exit(0)
except RuntimeError as e:
    print(f"❌ Erro: {e}")
    sys.exit(0)

# ============================================================================
# SALVAR
# ============================================================================

nome = f"{arquivo_escolhido.replace('.py','')}_RESULT_{tecnica}.py"
destino = os.path.join(pasta_combo, sanitize_filename(nome))

with open(destino, "w", encoding="utf-8") as f:
    f.write(res)

linha()
print("✅ Arquivo gerado com sucesso!")
print(f"📍 Local: {destino}")
linha()
