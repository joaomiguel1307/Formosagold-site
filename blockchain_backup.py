import hashlib
import time

class Bloco:
    def __init__(self, index, transacoes, hash_anterior):
        self.index = index
        self.transacoes = transacoes
        self.hash_anterior = hash_anterior
        self.timestamp = time.time()
        self.hash = self.calcular_hash()

    def calcular_hash(self):
        conteudo = str(self.index) + str(self.transacoes) + str(self.hash_anterior) + str(self.timestamp)
        return hashlib.sha256(conteudo.encode()).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain = [self.criar_bloco_genesis()]

    def criar_bloco_genesis(self):
        return Bloco(0, "Bloco Genesis - FormosaGold FMG", "0")

    def adicionar_bloco(self, transacoes):
        bloco_anterior = self.chain[-1]
        novo_bloco = Bloco(len(self.chain), transacoes, bloco_anterior.hash)
        self.chain.append(novo_bloco)

    def exibir_chain(self):
        for bloco in self.chain:
            print(f"Bloco #{bloco.index}")
            print(f"Transa??o: {bloco.transacoes}")
            print(f"Hash: {bloco.hash}")
            print(f"Hash anterior: {bloco.hash_anterior}")
            print("-" * 40)

fmg = Blockchain()
fmg.adicionar_bloco("Jo?o enviou 50 FMG para Maria")
fmg.adicionar_bloco("Maria enviou 20 FMG para Pedro")
fmg.exibir_chain()
