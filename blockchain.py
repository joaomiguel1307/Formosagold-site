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
        return Block(0, [{
            "from": "SYSTEM",
            "to": "45CLDmXsot469iov2X8TH6Ej5b7q",
            "amount": 10000000
        }], "0")

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
        halving = len(self.chain) // 300
        self.reward = max(5, int(50 / (2 ** halving)))
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

app = Flask(__name__)
fmg = Blockchain()

# ---------------------------------------------
# ROTAS ORIGINAIS
# ---------------------------------------------

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
        "address": w.address,
        "public_key": w.export_public(),
        "private_key": w.private_key.to_string().hex()
    })

@app.route("/transfer", methods=["POST"])
def transfer():
    data = request.json
    try:
        sk = SigningKey.from_string(bytes.fromhex(data["private_key"]), curve=SECP256k1)
        w = Wallet.__new__(Wallet)
        w.private_key = sk
        w.public_key = sk.get_verifying_key()
        w.address = w.generate_address()
        msg = f"{w.address}{data['to']}{data['amount']}"
        signature = w.sign(msg)
        result = fmg.add_transaction(w.address, data["to"], data["amount"], signature, w.export_public())
        return jsonify({"result": result, "from": w.address})
    except Exception as e:
        return jsonify({"result": f"erro: {str(e)}"})

@app.route("/manifest.json")
def manifest():
    return send_file("manifest.json")

@app.route("/sw.js")
def sw():
    return send_file("sw.js")

@app.route("/logo.svg")
def logo():
    return send_file("logo.svg")

# ---------------------------------------------
# NOVOS ENDPOINTS -- COMPATIBILIDADE WEB3/METAMASK
# ---------------------------------------------

# ID da sua rede -- n?mero ?nico para identificar sua blockchain
CHAIN_ID = 19307  # FMG Chain ID (pode mudar para qualquer n?mero acima de 1000)
CHAIN_ID_HEX = hex(CHAIN_ID)

@app.route("/rpc", methods=["POST", "OPTIONS"])
def rpc():
    """
    Endpoint JSON-RPC compat?vel com MetaMask e Web3.
    A MetaMask usa este endpoint para se comunicar com sua blockchain.
    """
    # Permite requisi??es do navegador (CORS)
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    data = request.json
    method = data.get("method")
    params = data.get("params", [])
    req_id = data.get("id", 1)

    result = None
    error = None

    # Retorna o ID da sua rede (necess?rio para MetaMask reconhecer)
    if method == "eth_chainId":
        result = CHAIN_ID_HEX

    # Retorna o n?mero do bloco atual
    elif method == "eth_blockNumber":
        result = hex(len(fmg.chain) - 1)

    # Retorna o saldo de um endere?o
    elif method == "eth_getBalance":
        address = params[0] if params else ""
        bal = fmg.get_balance(address)
        # Converte para Wei (unidade do Ethereum) multiplicando por 10^18
        result = hex(int(bal * (10 ** 18)))

    # Retorna informa??es de um bloco pelo n?mero
    elif method == "eth_getBlockByNumber":
        block_num = params[0] if params else "latest"
        if block_num == "latest":
            block = fmg.get_last()
        else:
            try:
                idx = int(block_num, 16)
                block = fmg.chain[idx] if idx < len(fmg.chain) else None
            except:
                block = None

        if block:
            result = {
                "number": hex(block.index),
                "hash": "0x" + block.hash,
                "parentHash": "0x" + block.previous_hash if block.previous_hash != "0" else "0x" + "0" * 64,
                "timestamp": hex(int(block.timestamp)),
                "transactions": block.transactions,
                "nonce": hex(block.nonce),
                "difficulty": hex(fmg.difficulty),
            }
        else:
            result = None

    # Retorna o n?mero de transa??es pendentes
    elif method == "eth_getTransactionCount":
        result = hex(len(fmg.pending))

    # Retorna informa??es da rede
    elif method == "net_version":
        result = str(CHAIN_ID)

    # Verifica se est? sincronizado
    elif method == "eth_syncing":
        result = False

    # Retorna lista de contas (vazia -- usu?rio gerencia as pr?prias carteiras)
    elif method == "eth_accounts":
        result = []

    # Retorna o pre?o do gas (taxa de transa??o -- zero na sua rede)
    elif method == "eth_gasPrice":
        result = "0x0"

    # Estima o gas de uma transa??o
    elif method == "eth_estimateGas":
        result = "0x5208"  # 21000 em hex (padr?o Ethereum)

    # Envia uma transa??o j? assinada
    elif method == "eth_sendRawTransaction":
        # Aceita a transa??o e retorna um hash simulado
        raw = params[0] if params else ""
        tx_hash = "0x" + hashlib.sha256(raw.encode()).hexdigest()
        result = tx_hash

    # Retorna o hash de uma transa??o
    elif method == "eth_getTransactionByHash":
        result = None  # Simplificado

    # M?todo n?o suportado
    else:
        error = {"code": -32601, "message": f"M?todo n?o suportado: {method}"}

    response = jsonify({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result,
        "error": error
    })
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@app.route("/network-info")
def network_info():
    """
    Retorna as informa??es para configurar a rede na MetaMask.
    Mostre essas informa??es no seu site para os usu?rios adicionarem a rede!
    """
    base_url = request.host_url.rstrip("/")
    return jsonify({
        "networkName": "Formosa Gold",
        "ticker": "FMG",
        "chainId": CHAIN_ID,
        "chainIdHex": CHAIN_ID_HEX,
        "rpcUrl": f"{base_url}/rpc",
        "explorerUrl": f"{base_url}/chain",
        "instrucoes": {
            "passo1": "Abra a MetaMask",
            "passo2": "Va em Configuracoes > Redes > Adicionar Rede",
            "passo3": f"Nome da Rede: Formosa Gold",
            "passo4": f"URL RPC: {base_url}/rpc",
            "passo5": f"ID da Cadeia: {CHAIN_ID}",
            "passo6": "Simbolo: FMG",
            "passo7": f"URL do Explorador: {base_url}/chain"
        }
    })


app.run(host="0.0.0.0", port=5000)

