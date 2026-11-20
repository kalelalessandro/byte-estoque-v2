"""Rotas do módulo de parceiros (clientes e fornecedores) do Byte Estoque.

Rotas (todas exigem login, igual ``GET /api/auth/me``):

    POST   /api/parceiros        cria um parceiro ("Inserir Parceiro Novo")
    GET    /api/parceiros        lista os parceiros da empresa ("Listar Parceiros")
    GET    /api/parceiros/<id>   dados completos + interações ("Acessar Parceiro")
    PATCH  /api/parceiros/<id>   altera dados e/ou relacionamento ("Alterar Parceiro")
    DELETE /api/parceiros/<id>   apaga o parceiro ("Apagar Parceiro")

As interações (contratos e compras com o parceiro: venda ao cliente, reembolso,
contrato de fornecimento, pagamento ao fornecedor) ficam em ``interactions.py``, sob
``/api/parceiros/<id>/interacoes``.

Regras principais (Documentação do Banco v1.2 e plano de testes, módulos PAR/INT):

- **Multi-tenant:** a empresa do parceiro vem SEMPRE do usuário logado
  (``g.usuario.id_empresa``), nunca do JSON. Parceiro de outra empresa responde 404.
  A empresa de um parceiro nunca é alterada.
- **Parceiro** é cliente, fornecedor ou ambos (``e_cliente`` / ``e_fornecedor``);
  ao menos um dos dois deve estar marcado.
- **E-mail e documento** (CPF/CNPJ sem pontuação) são opcionais e únicos POR EMPRESA
  (a mesma pessoa pode ser parceira de empresas diferentes). A comparação do banco
  ignora maiúsculas/acentos (``utf8mb4_0900_ai_ci``). Ausência é gravada como NULL.
- **Exclusão segura:** todas as FKs são ``ON DELETE RESTRICT``. Um parceiro com
  interações, operações ou títulos financeiros NÃO é apagado (409); assim nenhum
  histórico é perdido.

A validação/normalização dos campos fica em ``partners_rules.py``.
"""

from __future__ import annotations

from flask import Blueprint, g, request
from sqlalchemy import and_, func, select, text
from sqlalchemy.exc import IntegrityError

from ..core.auth_utils import (
    ler_json,
    login_obrigatorio,
    resposta_erro,
    resposta_ok,
)
from ..db import get_db
from ..db.models import Interacao, Parceiro, Usuario
from .partners_rules import MASCARA_DOCUMENTO, validar_criacao, validar_edicao

bp = Blueprint("partners", __name__)

# Paginação da listagem.
LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200

# Filtro ``?tipo=`` da listagem. "cliente" e "fornecedor" incluem quem é "ambos".
TIPOS_FILTRO = {"todos", "cliente", "fornecedor", "ambos"}

# Tabelas que referenciam ``parceiros`` (FK RESTRICT). Usadas só para dizer ao
# usuário POR QUE o parceiro não pode ser apagado. ``operacoes`` e
# ``titulos_financeiros`` ainda não têm módulo próprio, então consultamos por SQL.
_CONSULTAS_VINCULOS = {
    "interações": "SELECT COUNT(*) FROM interacoes WHERE id_parceiro = :id",
    "operações": "SELECT COUNT(*) FROM operacoes WHERE id_parceiro = :id",
    "títulos financeiros": (
        "SELECT COUNT(*) FROM titulos_financeiros WHERE id_parceiro = :id"
    ),
}


# ---------------------------------------------------------------------------
# Auxiliares (também usados por interactions.py)
# ---------------------------------------------------------------------------


def serializar_parceiro(parceiro: Parceiro) -> dict:
    """Parceiro -> dict JSON.

    ``tipo`` ("cliente", "fornecedor" ou "ambos") é só conveniência para a tela;
    a fonte de verdade são os dois booleanos.
    """
    if parceiro.e_cliente and parceiro.e_fornecedor:
        tipo = "ambos"
    elif parceiro.e_cliente:
        tipo = "cliente"
    else:
        tipo = "fornecedor"

    return {
        "id_parceiro": parceiro.id_parceiro,
        "id_empresa": parceiro.id_empresa,
        "nome": parceiro.nome,
        "documento": parceiro.documento,
        "email": parceiro.email,
        "cep": parceiro.cep,
        "e_cliente": bool(parceiro.e_cliente),
        "e_fornecedor": bool(parceiro.e_fornecedor),
        "tipo": tipo,
        "observacao": parceiro.observacao,
    }


def serializar_interacao(interacao: Interacao, usuario_nome: str | None) -> dict:
    """Interação -> dict JSON (data em ISO ``AAAA-MM-DD``)."""
    return {
        "interacao_id": interacao.interacao_id,
        "id_parceiro": interacao.id_parceiro,
        "id_usuario": interacao.id_usuario,
        "usuario_nome": usuario_nome,
        "ocorrencia": interacao.ocorrencia.isoformat(),
        "canal": interacao.canal,
        "descricao": interacao.descricao,
    }


def buscar_parceiro_da_empresa(id_parceiro: int, *, travar: bool = False) -> Parceiro | None:
    """Busca o parceiro filtrando pela empresa do usuário logado.

    Se existir mas for de OUTRA empresa, devolve ``None`` (a rota responde 404, sem
    revelar que o id existe). ``travar=True`` usa ``SELECT ... FOR UPDATE``: bloqueia a
    linha até o commit, evitando edições simultâneas e inserção de vínculos no meio
    de uma exclusão.
    """
    consulta = select(Parceiro).where(
        Parceiro.id_parceiro == id_parceiro,
        Parceiro.id_empresa == g.usuario.id_empresa,
    )
    if travar:
        consulta = consulta.with_for_update()
    return get_db().scalar(consulta)


def parceiro_nao_encontrado():
    return resposta_erro("Parceiro não encontrado.", 404)


def _listar_interacoes(id_parceiro: int) -> list[dict]:
    """Histórico do parceiro: mais recentes primeiro, com o nome do responsável."""
    linhas = get_db().execute(
        select(Interacao, Usuario.nome)
        .join(Usuario, Usuario.id_usuario == Interacao.id_usuario)
        .where(Interacao.id_parceiro == id_parceiro)
        .order_by(Interacao.ocorrencia.desc(), Interacao.interacao_id.desc())
    ).all()
    return [serializar_interacao(interacao, nome) for interacao, nome in linhas]


def _contar_vinculos(id_parceiro: int) -> dict[str, int]:
    """Quantos registros de cada tipo referenciam o parceiro (só os que existem)."""
    db = get_db()
    contagens = {
        rotulo: db.scalar(text(consulta), {"id": id_parceiro}) or 0
        for rotulo, consulta in _CONSULTAS_VINCULOS.items()
    }
    return {rotulo: total for rotulo, total in contagens.items() if total > 0}


def _conflitos_de_unicidade(
    id_empresa: int,
    *,
    email: str | None,
    documento: str | None,
    ignorar_id: int | None = None,
) -> dict[str, str]:
    """Campos (e-mail/documento) já usados por OUTRO parceiro da mesma empresa.

    É só a checagem amigável: as UNIQUEs do banco continuam sendo a garantia.
    """
    db = get_db()
    conflitos: dict[str, str] = {}

    for campo, valor, mensagem in (
        ("email", email, "E-mail já cadastrado."),
        ("documento", documento, "Documento já cadastrado."),
    ):
        if valor is None:
            continue
        consulta = select(Parceiro.id_parceiro).where(
            Parceiro.id_empresa == id_empresa,
            getattr(Parceiro, campo) == valor,
        )
        if ignorar_id is not None:
            consulta = consulta.where(Parceiro.id_parceiro != ignorar_id)
        if db.scalar(consulta.limit(1)) is not None:
            conflitos[campo] = mensagem
    return conflitos


def _resposta_duplicidade(conflitos: dict[str, str]):
    """409 com mensagem clara sobre qual campo já está em uso na empresa."""
    if "email" in conflitos and "documento" in conflitos:
        mensagem = "Já existe parceiro com este e-mail e este documento nesta empresa."
    elif "email" in conflitos:
        mensagem = "Já existe um parceiro com este e-mail nesta empresa."
    else:
        mensagem = "Já existe um parceiro com este documento nesta empresa."
    return resposta_erro(mensagem, 409, campos=conflitos)


def _ler_inteiro_query(nome: str, padrao: int, minimo: int, maximo: int):
    """Lê ``?nome=123`` da URL. Devolve ``(valor, None)`` ou ``(None, mensagem)``."""
    bruto = request.args.get(nome)
    if bruto is None or bruto == "":
        return padrao, None
    try:
        valor = int(bruto)
    except ValueError:
        return None, f"'{nome}' deve ser um número inteiro."
    if valor < minimo or valor > maximo:
        return None, f"'{nome}' deve estar entre {minimo} e {maximo}."
    return valor, None


# ---------------------------------------------------------------------------
# POST /api/parceiros  -> inserir parceiro novo
# ---------------------------------------------------------------------------


@bp.post("")
@login_obrigatorio
def criar_parceiro():
    dados, erro = ler_json()
    if erro is not None:
        return erro

    # 1) Formato/limites dos campos (sem tocar no banco).
    valores, erros = validar_criacao(dados)
    if erros:
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    db = get_db()
    id_empresa = g.usuario.id_empresa  # empresa vem da sessão, nunca do corpo

    # 2) E-mail/documento já usados nesta empresa?
    conflitos = _conflitos_de_unicidade(
        id_empresa, email=valores["email"], documento=valores["documento"]
    )
    if conflitos:
        return _resposta_duplicidade(conflitos)

    # 3) Grava.
    try:
        parceiro = Parceiro(id_empresa=id_empresa, **valores)
        db.add(parceiro)
        db.flush()  # gera o id_parceiro
        db.commit()
    except IntegrityError:
        # Corrida: outro request gravou o mesmo e-mail/documento entre a checagem e o INSERT.
        db.rollback()
        return resposta_erro(
            "Não foi possível criar o parceiro: e-mail ou documento já cadastrado "
            "nesta empresa.",
            409,
        )

    return resposta_ok(
        serializar_parceiro(parceiro), "Parceiro criado com sucesso.", 201
    )


# ---------------------------------------------------------------------------
# GET /api/parceiros  -> listar parceiros
# ---------------------------------------------------------------------------


@bp.get("")
@login_obrigatorio
def listar_parceiros():
    """Lista os parceiros da empresa do usuário.

    Parâmetros opcionais na URL:
      ``busca``  texto procurado no nome, e-mail ou documento (com ou sem pontuação);
      ``tipo``   ``cliente``, ``fornecedor``, ``ambos`` ou ``todos`` (padrão);
      ``limit``  itens por página (padrão 50, máximo 200);
      ``offset`` quantos itens pular (padrão 0).
    """
    limit, msg = _ler_inteiro_query("limit", LIMITE_PADRAO, 1, LIMITE_MAXIMO)
    if msg:
        return resposta_erro(msg, 422)
    offset, msg = _ler_inteiro_query("offset", 0, 0, 2_147_483_647)
    if msg:
        return resposta_erro(msg, 422)

    tipo = (request.args.get("tipo") or "todos").strip().lower()
    if tipo not in TIPOS_FILTRO:
        return resposta_erro(
            "'tipo' deve ser: todos, cliente, fornecedor ou ambos.", 422
        )

    filtros = [Parceiro.id_empresa == g.usuario.id_empresa]

    if tipo == "cliente":
        filtros.append(Parceiro.e_cliente.is_(True))
    elif tipo == "fornecedor":
        filtros.append(Parceiro.e_fornecedor.is_(True))
    elif tipo == "ambos":
        filtros.append(and_(Parceiro.e_cliente.is_(True), Parceiro.e_fornecedor.is_(True)))

    busca = (request.args.get("busca") or "").strip()
    if busca:
        # autoescape: "%" e "_" digitados pelo usuário valem como texto comum.
        condicao = Parceiro.nome.contains(busca, autoescape=True) | Parceiro.email.contains(
            busca, autoescape=True
        )
        # O documento é guardado sem pontuação: "529.982.247-25" deve achar "52998224725".
        documento_busca = MASCARA_DOCUMENTO.sub("", busca)
        if documento_busca:
            condicao = condicao | Parceiro.documento.contains(
                documento_busca, autoescape=True
            )
        filtros.append(condicao)

    db = get_db()
    total = db.scalar(select(func.count()).select_from(Parceiro).where(*filtros))
    parceiros = db.scalars(
        select(Parceiro)
        .where(*filtros)
        .order_by(Parceiro.nome, Parceiro.id_parceiro)
        .limit(limit)
        .offset(offset)
    ).all()

    return resposta_ok(
        {
            "parceiros": [serializar_parceiro(p) for p in parceiros],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


# ---------------------------------------------------------------------------
# GET /api/parceiros/<id>  -> acessar parceiro (dados + interações)
# ---------------------------------------------------------------------------


@bp.get("/<int:id_parceiro>")
@login_obrigatorio
def obter_parceiro(id_parceiro: int):
    parceiro = buscar_parceiro_da_empresa(id_parceiro)
    if parceiro is None:
        return parceiro_nao_encontrado()

    dados = serializar_parceiro(parceiro)
    dados["interacoes"] = _listar_interacoes(parceiro.id_parceiro)
    return resposta_ok(dados)


# ---------------------------------------------------------------------------
# PATCH /api/parceiros/<id>  -> alterar parceiro
# ---------------------------------------------------------------------------


@bp.patch("/<int:id_parceiro>")
@login_obrigatorio
def alterar_parceiro(id_parceiro: int):
    """Edição PARCIAL: envie só o que mudou. Ex.: ``{"e_fornecedor": true}``.

    Campos editáveis: ``nome``, ``documento``, ``email``, ``cep``, ``e_cliente``,
    ``e_fornecedor`` e ``observacao``. Enviar ``null`` em documento/e-mail/CEP/
    observação limpa o campo. A empresa do parceiro nunca muda.
    """
    dados, erro = ler_json()
    if erro is not None:
        return erro

    db = get_db()

    # Trava a linha (FOR UPDATE) e já filtra pela empresa do usuário.
    parceiro = buscar_parceiro_da_empresa(id_parceiro, travar=True)
    if parceiro is None:
        db.rollback()  # libera a transação aberta pelo SELECT
        return parceiro_nao_encontrado()

    # A regra "ao menos um relacionamento" depende dos valores atuais.
    valores, erros = validar_edicao(
        dados,
        e_cliente_atual=bool(parceiro.e_cliente),
        e_fornecedor_atual=bool(parceiro.e_fornecedor),
    )
    if erros:
        db.rollback()
        return resposta_erro(
            "Dados inválidos. Corrija os campos indicados.", 422, campos=erros
        )

    # E-mail/documento novos precisam ser únicos na empresa (ignorando o próprio parceiro).
    conflitos = _conflitos_de_unicidade(
        parceiro.id_empresa,
        email=valores.get("email"),
        documento=valores.get("documento"),
        ignorar_id=parceiro.id_parceiro,
    )
    if conflitos:
        db.rollback()
        return _resposta_duplicidade(conflitos)

    for campo, valor in valores.items():
        setattr(parceiro, campo, valor)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro(
            "Não foi possível salvar: e-mail ou documento já cadastrado nesta empresa.",
            409,
        )

    return resposta_ok(serializar_parceiro(parceiro), "Parceiro atualizado com sucesso.")


# ---------------------------------------------------------------------------
# DELETE /api/parceiros/<id>  -> apagar parceiro
# ---------------------------------------------------------------------------


@bp.delete("/<int:id_parceiro>")
@login_obrigatorio
def apagar_parceiro(id_parceiro: int):
    """Apaga um parceiro da empresa do usuário, desde que não tenha histórico.

    Com interações, operações ou títulos financeiros vinculados a resposta é 409 e
    informa quais são (``vinculos``). O banco (FK ``RESTRICT``) também bloqueia, caso
    algum vínculo apareça entre a checagem e o DELETE.
    """
    db = get_db()

    parceiro = buscar_parceiro_da_empresa(id_parceiro, travar=True)
    if parceiro is None:
        db.rollback()  # libera a transação aberta pelo SELECT
        return parceiro_nao_encontrado()

    vinculos = _contar_vinculos(parceiro.id_parceiro)
    if vinculos:
        db.rollback()
        return resposta_erro(
            "Não é possível apagar o parceiro: existem registros vinculados a ele ("
            + ", ".join(vinculos)
            + ").",
            409,
            vinculos=vinculos,
        )

    try:
        db.delete(parceiro)
        db.commit()
    except IntegrityError:
        db.rollback()
        return resposta_erro(
            "Não é possível apagar o parceiro: existem registros vinculados a ele.",
            409,
        )

    return resposta_ok({"id_parceiro": id_parceiro}, "Parceiro apagado com sucesso.")
