"""
Functions copied from pyethereum package to reduce dependencies
"""

# Imports
from rlp.sedes import big_endian_int
from Crypto.Hash import keccak
from py_ecc.secp256k1 import ecdsa_raw_sign
import coincurve
from rlp.utils import str_to_bytes


# Functions - ecsign
def big_endian_to_int(x):
    return big_endian_int.deserialize(str_to_bytes(x).lstrip(b'\x00'))


def safe_ord(value):
    if isinstance(value, int):
        return value
    else:
        return ord(value)


def ecsign(rawhash, key):
    if coincurve and hasattr(coincurve, 'PrivateKey'):
        pk = coincurve.PrivateKey(key)
        signature = pk.sign_recoverable(rawhash, hasher=None)
        v = safe_ord(signature[64]) + 27
        r = big_endian_to_int(signature[0:32])
        s = big_endian_to_int(signature[32:64])
    else:
        v, r, s = ecdsa_raw_sign(rawhash, key)
    return v, r, s


# Functions - sha3
def sha3(x):
    return keccak.new(digest_bits=256, data=x).digest()


# Functions - encode_int32
def int_to_big_endian(x):
    return big_endian_int.serialize(x)


def zpad(x, l):
    return b'\x00' * max(0, l - len(x)) + x


def encode_int32(v):
    return zpad(int_to_big_endian(v), 32)
