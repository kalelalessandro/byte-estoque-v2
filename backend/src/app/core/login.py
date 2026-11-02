import hashlib

def login(email, hashed_password):
    try:
        l_email = input("Insira seu email: ")
        l_password = input("Insira sua senha: ")
        l_hashed_password = hashlib.sha256(l_password.encode()).hexdigest()
        if l_email == email and l_hashed_password == hashed_password:
            print("Login bem-sucedido!")
        else:
            print("Email ou senha incorretos. Tente novamente.")
    except Exception as e:
        print(f"Ocorreu um erro durante o login: {e}")