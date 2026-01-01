#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ofuscador/Desofuscador avançado – 20 técnicas + modo TURBO
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
import hashlib
import struct

# ============================================================================
# UTILIDADES DE CONSOLE
# ============================================================================

def clear_console():
    os.system("cls" if os.name == "nt" else "clear")

def linha(tam=60, ch="="):
    print(ch * tam)

# ============================================================================
# Tentativa de importar AES (PyCryptodome)
# ============================================================================

try:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    HAVE_AES = True
except Exception:
    HAVE_AES = False

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

pasta_combo = "/sdcard/combo/"

clear_console()
linha()
print("🔐 OFUSCADOR PYTHON AVANÇADO v2.0")
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
    pad = block - (len(data) % block)
    return data + bytes([pad]) * pad

def gen_junk_code(n_funcs=4, max_lines=5):
    junk = ""
    for _ in range(n_funcs):
        fname = f"_junk_{random.randint(1000,9999)}"
        junk += f"def {fname}():\n"
        for _ in range(random.randint(1, max_lines)):
            junk += f"    _v = {random.randint(1,9999)}\n"
        junk += "    return None\n\n"
    return junk

def gen_random_var():
    chars = "abcdefghijklmnopqrstuvwxyz"
    return ''.join(random.choice(chars) for _ in range(random.randint(8,12)))

def gen_unicode_var():
    # Gera nomes de variáveis usando caracteres unicode válidos
    bases = ['α', 'β', 'γ', 'δ', 'ε', 'ζ', 'η', 'θ', 'ι', 'κ', 'λ', 'μ']
    return random.choice(bases) + str(random.randint(100,999))

# ============================================================================
# TÉCNICAS DE OFUSCAÇÃO ORIGINAIS (1-11)
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

def ofuscar_aes_base64(codigo):
    if not HAVE_AES:
        raise RuntimeError("PyCryptodome não instalado")
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
    if HAVE_AES:
        tecnicas.append(ofuscar_aes_base64)
    return random.choice(tecnicas)(codigo)

# ============================================================================
# NOVAS TÉCNICAS DE OFUSCAÇÃO (12-20)
# ============================================================================

def ofuscar_lambda_chain(codigo):
    """Técnica 12: Lambda aninhadas com múltiplas camadas"""
    comp = zlib.compress(codigo.encode())
    b64 = base64.b64encode(comp).decode()
    v1, v2, v3 = gen_random_var(), gen_random_var(), gen_random_var()
    return f"""
{v1}=lambda {v2}:__import__('zlib').decompress(__import__('base64').b64decode({v2}))
{v3}=(lambda:{v1}(b'{b64}').decode())
exec({v3}())
"""

def ofuscar_dict_encoding(codigo):
    """Técnica 13: Codificação baseada em dicionário"""
    # Cria um dicionário de substituição
    chars = list(set(codigo))
    random.shuffle(chars)
    mapping = {c: i for i, c in enumerate(chars)}
    encoded = [mapping[c] for c in codigo]
    
    chars_escaped = repr(chars)
    encoded_str = ','.join(map(str, encoded))
    
    return f"""
_c={chars_escaped}
_e=[{encoded_str}]
exec(''.join(_c[i] for i in _e))
"""

def ofuscar_multi_xor(codigo):
    """Técnica 14: XOR com múltiplas chaves rotativas"""
    keys = [random.randint(1, 255) for _ in range(4)]
    data = bytearray(codigo.encode())
    for i in range(len(data)):
        data[i] ^= keys[i % len(keys)]
    b64 = base64.b64encode(bytes(data)).decode()
    keys_str = ','.join(map(str, keys))
    return f"""
import base64
_k=[{keys_str}]
_d=bytearray(base64.b64decode('{b64}'))
for i in range(len(_d)):_d[i]^=_k[i%len(_k)]
exec(_d.decode())
"""

def ofuscar_string_split(codigo):
    """Técnica 15: Fragmentação de string com reconstrução"""
    comp = zlib.compress(codigo.encode())
    b64 = base64.b64encode(comp).decode()
    
    # Divide em pedaços aleatórios
    chunk_size = random.randint(20, 40)
    chunks = [b64[i:i+chunk_size] for i in range(0, len(b64), chunk_size)]
    
    # Embaralha com índices
    indices = list(range(len(chunks)))
    shuffled = list(zip(indices, chunks))
    random.shuffle(shuffled)
    
    parts = ','.join(f'({i},"{c}")' for i, c in shuffled)
    return f"""
import base64,zlib
_p=[{parts}]
_s=sorted(_p,key=lambda x:x[0])
_b=''.join(x[1] for x in _s)
exec(zlib.decompress(base64.b64decode(_b)).decode())
"""

def ofuscar_bytecode_raw(codigo):
    """Técnica 16: Bytecode raw com marshal comprimido"""
    compiled = compile(codigo, "<bytecode>", "exec")
    marshalled = marshal.dumps(compiled)
    compressed = lzma.compress(marshalled)
    b64 = base64.b64encode(compressed).decode()
    return f"""
import base64,lzma,marshal
_b=base64.b64decode('{b64}')
_d=lzma.decompress(_b)
_c=marshal.loads(_d)
exec(_c)
"""

def ofuscar_binary_repr(codigo):
    """Técnica 17: Representação binária com reconstrução"""
    binary = ''.join(format(ord(c), '08b') for c in codigo)
    comp = zlib.compress(binary.encode())
    b64 = base64.b64encode(comp).decode()
    return f"""
import base64,zlib
_b=zlib.decompress(base64.b64decode('{b64}')).decode()
_c=''.join(chr(int(_b[i:i+8],2)) for i in range(0,len(_b),8))
exec(_c)
"""

def ofuscar_unicode_vars(codigo):
    """Técnica 18: Variáveis com nomes unicode"""
    comp = zlib.compress(codigo.encode())
    b64 = base64.b64encode(comp).decode()
    
    # Variáveis unicode
    v_import = 'ℤℤℤ'
    v_data = 'αβγ'
    v_result = 'δεζ'
    
    return f"""
# -*- coding: utf-8 -*-
{v_import}=__import__
{v_data}='{b64}'
{v_result}={v_import}('zlib').decompress({v_import}('base64').b64decode({v_data}))
exec({v_result}.decode())
"""

def ofuscar_hash_validation(codigo):
    """Técnica 19: Validação por hash antes da execução"""
    comp = zlib.compress(codigo.encode())
    b64 = base64.b64encode(comp).decode()
    hash_val = hashlib.sha256(comp).hexdigest()
    
    return f"""
import base64,zlib,hashlib
_d=base64.b64decode('{b64}')
_h=hashlib.sha256(_d).hexdigest()
if _h=='{hash_val}':
    exec(zlib.decompress(_d).decode())
else:
    raise Exception('Integrity check failed')
"""

def ofuscar_nested_exec(codigo):
    """Técnica 20: Exec aninhado com múltiplas camadas"""
    # Camada 1
    comp1 = zlib.compress(codigo.encode())
    b64_1 = base64.b64encode(comp1).decode()
    layer1 = f"import base64,zlib;exec(zlib.decompress(base64.b64decode('{b64_1}')).decode())"
    
    # Camada 2
    comp2 = zlib.compress(layer1.encode())
    b64_2 = base64.b64encode(comp2).decode()
    layer2 = f"import base64,zlib;exec(zlib.decompress(base64.b64decode('{b64_2}')).decode())"
    
    # Camada 3
    comp3 = zlib.compress(layer2.encode())
    b64_3 = base64.b64encode(comp3).decode()
    
    return f"""
import base64,zlib
exec(zlib.decompress(base64.b64decode('{b64_3}')).decode())
"""

def ofuscar_chr_builder(codigo):
    """Técnica 21: Construção via chr() com operações matemáticas"""
    chars = []
    for c in codigo:
        val = ord(c)
        # Usa operação matemática aleatória
        op = random.randint(0, 3)
        if op == 0:
            offset = random.randint(1, 50)
            chars.append(f"chr({val + offset}-{offset})")
        elif op == 1:
            offset = random.randint(1, 50)
            chars.append(f"chr({val - offset}+{offset})")
        elif op == 2:
            mult = random.choice([2, 3, 4, 5])
            if val % mult == 0:
                chars.append(f"chr({val // mult}*{mult})")
            else:
                chars.append(f"chr({val})")
        else:
            chars.append(f"chr({val})")
    
    # Divide em linhas para não ficar muito longo
    chunk_size = 50
    chunks = [chars[i:i+chunk_size] for i in range(0, len(chars), chunk_size)]
    
    parts = []
    for i, chunk in enumerate(chunks):
        parts.append(f"_p{i}=" + '+'.join(chunk))
    
    join_vars = '+'.join(f'_p{i}' for i in range(len(chunks)))
    
    return '\n'.join(parts) + f"\nexec({join_vars})"

def ofuscar_base32_zlib(codigo):
    """Técnica 22: Base32 + Zlib + Marshal"""
    comp = marshal.dumps(compile(codigo, "<b32>", "exec"))
    comp = zlib.compress(comp)
    b32 = base64.b32encode(comp).decode()
    return f"""
import base64,zlib,marshal
exec(marshal.loads(zlib.decompress(base64.b32decode('{b32}'))))
"""

def ofuscar_hex_xor_chain(codigo):
    """Técnica 23: Hex + XOR em cadeia"""
    data = codigo.encode()
    key = random.randint(1, 255)
    
    # XOR em cadeia (cada byte XOR com anterior)
    result = bytearray()
    prev = key
    for b in data:
        xored = b ^ prev
        result.append(xored)
        prev = xored
    
    hex_data = result.hex()
    return f"""
_k={key}
_h='{hex_data}'
_d=bytes.fromhex(_h)
_r=bytearray()
_p=_k
for b in _d:
    _x=b^_p
    _r.append(_x)
    _p=b
exec(_r.decode())
"""

def ofuscar_compressed_layers(codigo):
    """Técnica 24: Múltiplas camadas de compressão diferentes"""
    # LZMA -> Zlib -> Base85
    comp1 = lzma.compress(codigo.encode())
    comp2 = zlib.compress(comp1)
    b85 = base64.b85encode(comp2).decode()
    return f"""
import base64,zlib,lzma
_d=base64.b85decode('{b85}')
_d=zlib.decompress(_d)
_d=lzma.decompress(_d)
exec(_d.decode())
"""

def ofuscar_attribute_trick(codigo):
    """Técnica 25: Uso de getattr e setattr para esconder imports"""
    comp = zlib.compress(codigo.encode())
    b64 = base64.b64encode(comp).decode()
    return f"""
_=__builtins__
_g=getattr(_,'__import__')
_b=_g('base64')
_z=_g('zlib')
_d=getattr(_b,'b64decode')('{b64}')
_r=getattr(_z,'decompress')(_d)
getattr(_,'exec')(_r.decode())
"""

# ============================================================================
# MENU (COM ESCALAS)
# ============================================================================

linha()
print("🎯 Escolha uma técnica de ofuscação (Escala 1–10):\n")
print("""
 1  = Base64 + Zlib + Marshal        [4/10]
 2  = ROT13 + HEX                    [1/10]
 3  = Base85 + Zlib                  [3/10]
 4  = XOR + Base64                   [4/10]
 5  = Triple Layer                   [7/10]
 6  = Multilayer Heavy               [8/10]
 7  = AES-CBC + Base64               [9/10]
 8  = LZMA + Base64                  [5/10]
 9  = Junk Code + Compress           [6/10]
10  = Misturador Aleatório           [8/10]
11  = Reverse + B64 + Zlib + Marshal [7/10]

──────── NOVAS TÉCNICAS ────────

12  = Lambda Chain                   [6/10]
13  = Dict Encoding                  [5/10]
14  = Multi-Key XOR                  [7/10]
15  = String Split & Shuffle         [7/10]
16  = Bytecode Raw + LZMA            [8/10]
17  = Binary Representation          [4/10]
18  = Unicode Variables              [5/10]
19  = Hash Validation                [6/10]
20  = Nested Exec (3 layers)         [8/10]
21  = Chr Builder Math               [6/10]
22  = Base32 + Zlib + Marshal        [5/10]
23  = Hex XOR Chain                  [7/10]
24  = Compressed Layers              [8/10]
25  = Attribute Trick                [7/10]

0  = TURBO ULTIMATE (todas)         [10/10]
""")
linha()

tecnica = input("👉 Técnica escolhida: ").strip()

# ============================================================================
# PROCESSAMENTO
# ============================================================================

if tecnica == "1":   res = ofuscar_base64_zlib_marshal(conteudo_original)
elif tecnica == "2": res = ofuscar_rot13_hex(conteudo_original)
elif tecnica == "3": res = ofuscar_base85(conteudo_original)
elif tecnica == "4": res = ofuscar_xor_base64(conteudo_original)
elif tecnica == "5": res = ofuscar_triple_layer(conteudo_original)
elif tecnica == "6": res = ofuscar_multilayer_heavy(conteudo_original)
elif tecnica == "7": res = ofuscar_aes_base64(conteudo_original)
elif tecnica == "8": res = ofuscar_lzma_base64(conteudo_original)
elif tecnica == "9": res = ofuscar_with_junk(conteudo_original)
elif tecnica == "10": res = ofuscar_misturador_aleatorio(conteudo_original)
elif tecnica == "11": res = ofuscar_reverse_b64_zlib_marshal(conteudo_original)
elif tecnica == "12": res = ofuscar_lambda_chain(conteudo_original)
elif tecnica == "13": res = ofuscar_dict_encoding(conteudo_original)
elif tecnica == "14": res = ofuscar_multi_xor(conteudo_original)
elif tecnica == "15": res = ofuscar_string_split(conteudo_original)
elif tecnica == "16": res = ofuscar_bytecode_raw(conteudo_original)
elif tecnica == "17": res = ofuscar_binary_repr(conteudo_original)
elif tecnica == "18": res = ofuscar_unicode_vars(conteudo_original)
elif tecnica == "19": res = ofuscar_hash_validation(conteudo_original)
elif tecnica == "20": res = ofuscar_nested_exec(conteudo_original)
elif tecnica == "21": res = ofuscar_chr_builder(conteudo_original)
elif tecnica == "22": res = ofuscar_base32_zlib(conteudo_original)
elif tecnica == "23": res = ofuscar_hex_xor_chain(conteudo_original)
elif tecnica == "24": res = ofuscar_compressed_layers(conteudo_original)
elif tecnica == "25": res = ofuscar_attribute_trick(conteudo_original)
elif tecnica == "0":
    # TURBO ULTIMATE - aplica múltiplas técnicas em sequência
    seq = [
        ofuscar_with_junk,
        ofuscar_lzma_base64,
        ofuscar_xor_base64,
        ofuscar_base85,
        ofuscar_multi_xor,
        ofuscar_compressed_layers,
        ofuscar_nested_exec,
        ofuscar_multilayer_heavy,
        ofuscar_triple_layer,
        ofuscar_reverse_b64_zlib_marshal,
    ]
    out = conteudo_original
    for fn in seq:
        out = fn(out)
    if HAVE_AES:
        out = ofuscar_aes_base64(out)
    res = out
else:
    print("❌ Técnica inválida.")
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
