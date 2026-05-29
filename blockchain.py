import hashlib
import json
import time
import base64
import base58
import os
import psycopg2
from flask import Flask, request, jsonify, send_file
from ecdsa import SigningKey, VerifyingKey, SECP256k1

def get_db():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            idx INTEGER PRIMARY KEY,
            data JSONB NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def save_block(block_dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO blocks (idx, data) VALUES (%s, %s) ON CONFLICT (idx) DO UPDATE SET data=%s",
        (block_dict["index"], json.dumps(block_dict), json.dumps(block_dict))
    )
    conn.commit()
    cur.close()
    conn.close()

def load_chain():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT data FROM blocks ORDER BY idx")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]

# CARTEIRA
class Wallet:
    def __init__(self):
        self.private_key = SigningKey.generate(curve=SECP256k1)
        self.public_key = self.private_key.get_verifying_key()
        self.address = self.generate_address()

    def generate_address(self):
        pub = self.public_key.to_string()
        sha = hashlib.sha256(pub).digest()
        ripemd = hashlib.new("ripemd160")
        ripemd.update(sha)
        return base58.b58encode(ripemd.digest()).decode()

    def sign(self, message):
        signature = self.private_key.sign(str(message).encode())
        return base64.b64encode(signature).decode()

    def export_public(self):
        return self.public_key.to_string().hex()

def verify_signature(message, signature, public_key):
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key), curve=SECP256k1)
        return vk.verify(base64.b64decode(signature), str(message).encode())
    except:
        return False

# BLOCK
class Block:
    def __init__(self, index, transactions, previous_hash, nonce=0, timestamp=None, hash=None):
        self.index = index
        self.timestamp = timestamp or time.time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = hash or self.calculate_hash()

    def calculate_hash(self):
        data = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }, sort_keys=True).encode()
        return hashlib.sha256(data).hexdigest()

    def mine(self, difficulty):
        target = "0" * difficulty
        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash
        }

# BLOCKCHAIN
class Blockchain:
    def __init__(self):
        self.difficulty = 3
        self.reward = 50
        self.pending = []
        init_db()
        chain = load_chain()
        if chain:
            self.chain = [self._dict_to_block(b) for b in chain]
        else:
            genesis = self.create_genesis()
            self.chain = [genesis]
            save_block(genesis.to_dict())

    def _dict_to_block(self, d):
        return Block(d["index"], d["transactions"], d["previous_hash"], d["nonce"], d["timestamp"], d["hash"])

    def create_genesis(self):
        return Block(0, [], "0")

    def get_last(self):
        return self.chain[-1]

    def get_balance(self, address):
        balance = 0
        for block in self.chain:
            for tx in block.transactions:
                if tx["from"] == address:
                    balance -= tx["amount"]
                if tx["to"] == address:
                    balance += tx["amount"]
        return balance

    def add_transaction(self, sender, receiver, amount, signature, pubkey):
        if sender != "SYSTEM":
            msg = f"{sender}{receiver}{amount}"
            if not verify_signature(msg, signature, pubkey):
                return "assinatura invalida"
            if self.get_balance(sender) < amount:
                return "saldo insuficiente"
        self.pending.append({
            "from": sender,
            "to": receiver,
            "amount": amount,
            "signature": signature,
            "public_key": pubkey
        })
        return "ok"

    def mine_pending(self, miner):
        self.pending.append({
            "from": "SYSTEM",
            "to": miner,
            "amount": self.reward
        })
        block = Block(len(self.chain), self.pending, self.get_last().hash)
        block.mine(self.difficulty)
        self.chain.append(block)
        save_block(block.to_dict())
        self.pending = []

# API
app = Flask(__name__)
fmg = Blockchain()

@app.route("/")
def index():
    return send_file("Formosagold.html")

@app.route("/chain")
def chain():
    return jsonify([b.to_dict() for b in fmg.chain])

@app.route("/balance/<addr>")
def balance(addr):
    return jsonify({"saldo": fmg.get_balance(addr)})

@app.route("/transaction", methods=["POST"])
def tx():
    data = request.json
    result = fmg.add_transaction(data["from"], data["to"], data["amount"], data["signature"], data["public_key"])
    return jsonify({"result": result})

@app.route("/mine")
def mine():
    miner = request.args.get("miner")
    fmg.mine_pending(miner)
    return jsonify({"status": "mined", "miner": miner})

@app.route("/wallet/new")
def new_wallet():
    w = Wallet()
    return jsonify({
        "endere?o": w.address,
        "public_key": w.export_public(),
        "chave_privada": w.private_key.to_string().hex()
    })

# START
@app.route("/transfer", methods=["POST"])
def transfer():
    data = request.json
    try:
        sk = SigningKey.from_string(
            bytes.fromhex(data["private_key"]),
            curve=SECP256k1
        )
        w = Wallet.__new__(Wallet)
        w.private_key = sk
        w.public_key = sk.get_verifying_key()
        w.address = w.generate_address()
        msg = f"{w.address}{data['to']}{data['amount']}"
        signature = w.sign(msg)
        result = fmg.add_transaction(
            w.address, data["to"],
            data["amount"], signature,
            w.export_public()
        )
        return jsonify({"result": result, "from": w.address})
    except Exception as e:
        return jsonify({"result": f"erro: {str(e)}"})
app.run(host="0.0.0.0", port=5000)
