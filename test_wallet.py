from wallet import Wallet

# Criar duas carteiras
alice = Wallet()
bob = Wallet()

print("\n=== CARTEIRA ALICE ===")
print("Endere?o:", alice.address)

print("\n=== CARTEIRA BOB ===")
print("Endere?o:", bob.address)

# Mensagem de transa??o
msg = f"{alice.address}{bob.address}50"

# Assinar transa??o
signature = alice.sign(msg)

print("\n=== TRANSA??O ASSINADA ===")
print("Mensagem:", msg)
print("Assinatura:", signature)

# Exportar chaves (teste)
print("\n=== CHAVES ALICE ===")
print(alice.export_keys())
