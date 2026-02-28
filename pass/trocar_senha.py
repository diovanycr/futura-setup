import hashlib
import re
import os

print()
print("=" * 50)
print("  FUTURA SETUP - TROCAR SENHA")
print("=" * 50)
print()

# Localiza o main.py na mesma pasta do script
pasta = os.path.dirname(os.path.abspath(__file__))
main_path = os.path.join(pasta, "..", "main.py")

if not os.path.exists(main_path):
    print("[ERRO] main.py nao encontrado em:", main_path)
    input("\nPressione Enter para sair...")
    exit(1)

senha = input("  Digite a nova senha: ").strip()

if not senha:
    print("\n[ERRO] Senha nao pode ser vazia.")
    input("\nPressione Enter para sair...")
    exit(1)

# Gerar hash
novo_hash = hashlib.sha256(senha.encode()).hexdigest()
print(f"\n  Hash gerado: {novo_hash}")

# Ler main.py
with open(main_path, "r", encoding="utf-8") as f:
    conteudo = f.read()

# Verificar se encontrou a linha
if '_SENHA_HASH' not in conteudo:
    print("\n[ERRO] Linha _SENHA_HASH nao encontrada no main.py.")
    input("\nPressione Enter para sair...")
    exit(1)

# Substituir
nova_linha = f'_SENHA_HASH = "{novo_hash}"  # senha: {senha}'
conteudo_novo = re.sub(r'_SENHA_HASH = "[^"]*"[^\n]*', nova_linha, conteudo)

# Salvar
with open(main_path, "w", encoding="utf-8") as f:
    f.write(conteudo_novo)

print()
print("=" * 50)
print("  SENHA ALTERADA COM SUCESSO!")
print("=" * 50)
print()
print(f"  Nova senha: {senha}")
print()
print("  Rode o build.bat para gerar o novo .exe.")
print()
input("Pressione Enter para sair...")
