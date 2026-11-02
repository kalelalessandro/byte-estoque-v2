from core.signup import *
from core.login import *

print("Bem-vindo ao sistema ByteEstoque!")
print("================================")
print("1. Criar usuário")
print("2. Fazer login")
print("3. Criar parceiro")
print("4. Sair")

while True:
    try:
        choice = int(input("Escolha uma opção (1-4): "))
        if choice == 1:
            name, email, hashed_password, admin = create_user()
        if choice == 2:
            login(email, hashed_password)
        if choice == 3:
            create_partner()
        if choice == 4:
            print("Saindo do sistema. Até logo!")
            exit()
            break
    except ValueError:
        print("Opção inválida. Por favor, insira um número entre 1 e 4.")