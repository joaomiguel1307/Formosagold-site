import base64
import base58
import hashlib
from ecdsa import SigningKey, SECP256k1


class Wallet:

    def __init__(self):

        self.private_key = SigningKey.generate(curve=SECP256k1)
        self.public_key = self.private_key.get_verifying_key()

        self.address = self.generate_address()

    def generate_address(self):

        pub_key_bytes = self.public_key.to_string()

        sha = hashlib.sha256(pub_key_bytes).digest()

        ripemd = hashlib.new('ripemd160')
        ripemd.update(sha)

        return base58.b58encode(ripemd.digest()).decode()

    def sign(self, message):

        signature = self.private_key.sign(str(message).encode())
        return base64.b64encode(signature).decode()

    def export_keys(self):

        return {
            "private_key": self.private_key.to_string().hex(),
            "public_key": self.public_key.to_string().hex(),
            "address": self.address
        }
