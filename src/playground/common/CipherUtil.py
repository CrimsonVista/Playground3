'''
Created on Mar 29, 2014

@author: sethjn
'''
import sys
sys.path.append("../..")
import hashlib, hmac

from cryptography import x509
from cryptography.x509 import Certificate
from cryptography.x509.oid import NameOID

from cryptography.exceptions import InvalidSignature

from cryptography.hazmat.backends import default_backend
backend = default_backend()

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes

from cryptography.hazmat.primitives.asymmetric.padding import PSS, OAEP, MGF1, PKCS1v15
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

# For other modules. Should be built into this module...
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import CBC

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from cryptography.hazmat.primitives.padding import PKCS7

# In case we want to change this to 512 in the future or anything else
SHA = hashlib.sha256

def PBKDF2(password, salt):
    kdf = PBKDF2HMAC(
         algorithm=hashes.SHA256(),
         length=32,
         salt=salt,
         iterations=10000,
         backend=backend
    )
    return kdf.derive(bytes(password,"utf-8"))

class CIPHER_AES128_CBC(object):
    def __init__(self, key, iv):
        cipher = Cipher(AES(key), CBC(iv), backend)
        self.encrypter = cipher.encryptor()
        self.decrypter = cipher.decryptor()
        self.block_size = 128
        
    def encrypt(self, data):
        padder = PKCS7(self.block_size).padder()
        paddedData = padder.update(data) + padder.finalize()
        return self.encrypter.update(paddedData) + self.encrypter.finalize()

    def decrypt(self, data):
        paddedData = self.decrypter.update(data) + self.encrypter.finalize()
        unpadder = PKCS7(self.block_size).unpadder()
        return unpadder.update(paddedData) + unpadder.finalize()
    
class MAC_HMAC_SHA1(object):
    MAC_SIZE = 20
    def __init__(self, key):
        self.__key = key
    
    def mac(self, data):
        mac = hmac.new(self.__key, digestmod="sha1")
        mac.update(data)
        return mac.digest()
    
    def verifyMac(self, data, checkMac):
        mac = self.mac(data)
        return mac == checkMac


class RSA_SIGNATURE_MAC(object):
    MAC_SIZE = 256

    def __init__(self, key):
        if isinstance(key, RSAPrivateKey):
            self.signer = key.sign
            self.verifier = key.public_key().verify
        elif isinstance(key, RSAPublicKey):
            self.signer = None
            self.verifier = key.verify

    def sign(self, data):
        return self.mac(data)

    def mac(self, data):
        rsamac = self.signer(
            data,
            # PSS(
            #     mgf=MGF1(hashes.SHA256()),
            #     salt_length=PSS.MAX_LENGTH
            # ),
            PKCS1v15(),
            hashes.SHA256()
        )
        return rsamac

    def verify(self, data, signature):
        return self.verifyMac(data, signature)

    def verifyMac(self, data, checkMac):
        try:
            self.verifier(
                checkMac,
                data,
                # PSS(
                #     mgf=MGF1(hashes.SHA256()),
                #     salt_length=PSS.MAX_LENGTH
                # ),
                PKCS1v15(),
                hashes.SHA256()
            )
            return True
        except InvalidSignature:
            return False


class EncryptThenMac(object):
    @staticmethod
    def CreateMode(encMode, macMode):
        return lambda k_enc, iv, k_mac: EncryptThenMac(encMode, macMode, k_enc, iv, k_mac)
    
    def __init__(self, encMode, macMode, k_enc, iv, k_mac):
        self.encrypter = encMode(k_enc, iv)
        self.mac = macMode(k_mac)
    
    def encrypt(self, data):
        cipherText = self.encrypter.encrypt(data)
        return cipherText + self.mac.mac(cipherText)
    
    def decrypt(self, data):
        cipherText, storedMac = data[:-self.mac.MAC_SIZE], data[-self.mac.MAC_SIZE:]
        if not self.mac.verifyMac(cipherText, storedMac):
            return None
        return self.encrypter.decrypt(cipherText)


EncryptThenHmac = EncryptThenMac.CreateMode(CIPHER_AES128_CBC, MAC_HMAC_SHA1)
EncryptThenRsaSign = EncryptThenMac.CreateMode(CIPHER_AES128_CBC, RSA_SIGNATURE_MAC)


# Takes an RSAPrivateKey object and message and returns a signature
def DefaultSign(msg, rsaPrivKey):
    return rsaPrivKey.sign(
        msg,
        PSS(
            mgf=MGF1(hashes.SHA256()),
            salt_length=PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )

# Intended for loading a private key
# Returns: RSAPrivateKey
def loadPrivateKeyFromPemFile(path):
    with open(path, "rb") as key_file:
        return getPrivateKeyFromPemBytes(key_file.read())

def getPrivateKeyFromPemBytes(pem_data):
    private_key = serialization.load_pem_private_key(
        pem_data,
        password=None,
        backend=backend
    )
    return private_key


# Loads an X509 certificate from file
# Returns: Certificate
def loadCertFromFile(path):
    with open(path, "rb") as cert_file:
        return getCertFromBytes(cert_file.read())


# Loads an X509 certificate from given bytes
# Returns: Certificate
def getCertFromBytes(pem_data):
    return x509.load_pem_x509_certificate(pem_data, backend)


def serializePrivateKey(private_key):
    assert(isinstance(private_key, RSAPrivateKey))
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )
    return pem

def serializeCert(cert):
    assert(isinstance(cert, x509.Certificate))
    x509bytes = cert.public_bytes(serialization.Encoding.PEM)
    return x509bytes

# Takes a Certificate object and returns a dictionary of named values
def getCertIssuer(cert):
    assert(isinstance(cert, Certificate))
    d = dict()
    for a in list(cert.issuer):
        d[a.oid._name] = a.value
    return d

# Takes a Certificate object and returns a dictionary of named values
def getCertSubject(cert):
    assert(isinstance(cert, Certificate))
    d = dict()
    for a in list(cert.subject):
        d[a.oid._name] = a.value
    return d

# Takes a list of Certificate objects and checks if
# each one is signed by the next.
# WARNING: This ONLY checks signatures, which is NOT
# sufficient to ensure trust.
# Ask yourself: what else is needed?
# Intentionally ommitting important checks for science
def ValidateCertChainSigs(certs):
    for i in range(len(certs)-1):
        this = certs[i]
        issuer = RSA_SIGNATURE_MAC(certs[i+1].public_key())
        if not issuer.verify(this.tbs_certificate_bytes, this.signature):
            return False
    return True
