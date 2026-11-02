import hashlib

def create_user():
    name = input("Insira seu nome: ")
    email = input("Insira seu email: ")
    password = input("Insira sua senha: ")
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    admin = input("Você é admin? (yes/no): ").lower() == "yes"
    return name, email, hashed_password, admin

def create_partner():
    p_name = input("Insira o nome do parceiro: ")
    p_email = input("Insira o email do parceiro: ")
    try:
        p_document = int(input("Insira o CNPJ/CPF do parceiro (somente números): "))
    except ValueError:
        print("CNPJ/CPF inválido. Por favor, insira apenas números.")
        return None
    try:
        p_address = int(input("Insira o endereço do parceiro (somente números): "))
    except ValueError:
        print("Endereço inválido. Por favor, insira apenas números.")
        return None
    p_is_client= input("O parceiro é cliente? (yes/no): ").lower() == "yes"
    p_is_supplier = input("O parceiro é fornecedor? (yes/no): ").lower() == "yes"
    return p_name, p_email, p_document, p_address, p_is_client, p_is_supplier