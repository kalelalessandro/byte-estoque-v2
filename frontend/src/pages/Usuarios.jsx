/**
 * Gestão de usuários/funcionários da empresa.
 *
 * O Dono aparece na lista e pode criar/editar/apagar funcionários. Funcionários
 * têm as mesmas funções do Dono no sistema, mas não podem apagar a conta do Dono;
 * ninguém apaga a própria conta. O backend é a fonte de verdade das permissões.
 */
import { useEffect, useState } from 'react'
import { api, mensagemDeErro } from '../api'
import Aviso from '../components/Aviso'
import Icone from '../components/Icone'
import Modal from '../components/Modal'

function iniciais(nome = '') {
  const partes = nome.trim().split(/\s+/).filter(Boolean)
  return (partes[0]?.[0] || 'U') + (partes[1]?.[0] || '')
}

function ordenar(lista) {
  return [...lista].sort((a, b) => {
    if (a.dono !== b.dono) return a.dono ? -1 : 1
    return (a.nome || '').localeCompare(b.nome || '', 'pt-BR')
  })
}

function formularioVazio() {
  return { nome: '', email: '', telefone: '', senha: '' }
}

export default function Usuarios({ usuario }) {
  const [usuarios, setUsuarios] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')
  const [modalAberto, setModalAberto] = useState(false)
  const [editando, setEditando] = useState(null)
  const [formulario, setFormulario] = useState(formularioVazio)
  const [salvando, setSalvando] = useState(false)
  const [erroFormulario, setErroFormulario] = useState('')

  useEffect(() => {
    let ativo = true
    api.usuarios
      .listar()
      .then((resposta) => {
        if (!ativo) return
        setUsuarios(ordenar(resposta.dados.usuarios))
        setErro('')
      })
      .catch((falha) => {
        if (ativo) setErro(mensagemDeErro(falha))
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [])

  function abrirNovo() {
    setEditando(null)
    setFormulario(formularioVazio())
    setErroFormulario('')
    setAviso('')
    setModalAberto(true)
  }

  function abrirEdicao(funcionario) {
    setEditando(funcionario)
    setFormulario({
      nome: funcionario.nome || '',
      email: funcionario.email || '',
      telefone: funcionario.telefone || '',
      senha: '',
    })
    setErroFormulario('')
    setAviso('')
    setModalAberto(true)
  }

  function fecharModal() {
    if (salvando) return
    setModalAberto(false)
    setEditando(null)
    setErroFormulario('')
  }

  function alterarCampo(campo, valor) {
    setFormulario((atual) => ({ ...atual, [campo]: valor }))
  }

  function aplicarNaLista(salvo) {
    setUsuarios((atuais) => {
      const existe = atuais.some(
        (item) => item.id_usuario === salvo.id_usuario,
      )
      if (existe) {
        return ordenar(
          atuais.map((item) =>
            item.id_usuario === salvo.id_usuario ? salvo : item,
          ),
        )
      }
      return ordenar([...atuais, salvo])
    })
  }

  async function salvar(evento) {
    evento.preventDefault()
    setErroFormulario('')

    if (!formulario.nome.trim() || !formulario.email.trim()) {
      setErroFormulario('Nome e e-mail são obrigatórios.')
      return
    }
    if (!editando && !formulario.senha) {
      setErroFormulario('Defina uma senha para o novo funcionário.')
      return
    }

    const dados = {
      nome: formulario.nome.trim(),
      email: formulario.email.trim(),
      telefone: formulario.telefone.trim() || null,
    }
    if (formulario.senha) dados.senha = formulario.senha

    setSalvando(true)
    try {
      const resposta = editando
        ? await api.usuarios.editar(editando.id_usuario, dados)
        : await api.usuarios.criar(dados)
      aplicarNaLista(resposta.dados)
      setAviso(
        editando
          ? 'Usuário atualizado com sucesso.'
          : 'Funcionário cadastrado com sucesso.',
      )
      setModalAberto(false)
      setEditando(null)
    } catch (falha) {
      setErroFormulario(mensagemDeErro(falha))
    } finally {
      setSalvando(false)
    }
  }

  async function excluir(funcionario) {
    if (funcionario.dono || funcionario.id_usuario === usuario?.id_usuario) {
      return
    }
    const confirmado = window.confirm(
      `Excluir o funcionário "${funcionario.nome}"? Ele perderá o acesso ao sistema.`,
    )
    if (!confirmado) return

    setErro('')
    setAviso('')
    try {
      await api.usuarios.excluir(funcionario.id_usuario)
      setUsuarios((atuais) =>
        atuais.filter((item) => item.id_usuario !== funcionario.id_usuario),
      )
      setAviso('Funcionário excluído com sucesso.')
    } catch (falha) {
      setErro(mensagemDeErro(falha))
    }
  }

  const podeExcluir = (funcionario) =>
    !funcionario.dono && funcionario.id_usuario !== usuario?.id_usuario

  // Funcionário não altera a conta do Dono; o Dono continua podendo editar todos.
  const podeEditar = (funcionario) => !funcionario.dono || usuario?.dono

  const dono = usuarios.find((item) => item.dono)

  return (
    <div className="pagina">
      <header className="pagina__cabecalho">
        <div>
          <span className="rotulo-secao">Pessoas</span>
          <h2>Equipe</h2>
          <p>
            Gerencie os usuários da empresa. Funcionários têm acesso aos mesmos
            dados e funções do dono, mas não podem excluí-lo.
          </p>
        </div>
        <div className="pagina__acoes">
          <button
            className="botao botao--primario"
            type="button"
            onClick={abrirNovo}
          >
            <Icone nome="mais" />
            Novo funcionário
          </button>
        </div>
      </header>

      {aviso ? <Aviso tipo="sucesso">{aviso}</Aviso> : null}
      {erro ? <Aviso>{erro}</Aviso> : null}

      {dono ? (
        <div className="painel painel--dono">
          <span className="usuario__avatar" aria-hidden="true">
            {iniciais(dono.nome).toUpperCase()}
          </span>
          <div>
            <span className="rotulo-secao">Dono da empresa</span>
            <strong>{dono.nome}</strong>
            <small>{dono.email}</small>
          </div>
          <span className="badge badge--dono">Dono</span>
        </div>
      ) : null}

      <section className="painel">
        <div className="painel__topo">
          <h3>Usuários com acesso</h3>
          <span className="contador">
            {usuarios.length} {usuarios.length === 1 ? 'usuário' : 'usuários'}
          </span>
        </div>

        {carregando ? (
          <div className="estado-carregando">Carregando equipe…</div>
        ) : usuarios.length === 0 ? (
          <div className="estado-vazio">
            <Icone nome="usuarios" />
            <h3>Nenhum usuário encontrado</h3>
          </div>
        ) : (
          <div className="tabela-wrap">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>E-mail</th>
                  <th>Telefone</th>
                  <th>Perfil</th>
                  <th aria-label="Ações" />
                </tr>
              </thead>
              <tbody>
                {usuarios.map((funcionario) => (
                  <tr key={funcionario.id_usuario}>
                    <td>
                      <span className="usuario-linha">
                        <span className="usuario__avatar" aria-hidden="true">
                          {iniciais(funcionario.nome).toUpperCase()}
                        </span>
                        <strong className="tabela__destaque">
                          {funcionario.nome}
                          {funcionario.id_usuario === usuario?.id_usuario ? (
                            <small className="usuario__voce"> (você)</small>
                          ) : null}
                        </strong>
                      </span>
                    </td>
                    <td>{funcionario.email}</td>
                    <td>{funcionario.telefone || '—'}</td>
                    <td>
                      <span
                        className={`badge ${
                          funcionario.dono ? 'badge--dono' : 'badge--funcionario'
                        }`}
                      >
                        {funcionario.dono ? 'Dono' : 'Funcionário'}
                      </span>
                    </td>
                    <td>
                      <div className="tabela__acoes">
                        {podeEditar(funcionario) ? (
                          <button
                            className="botao-icone"
                            type="button"
                            onClick={() => abrirEdicao(funcionario)}
                            aria-label={`Editar ${funcionario.nome}`}
                            title="Editar"
                          >
                            <Icone nome="lapis" />
                          </button>
                        ) : null}
                        {podeExcluir(funcionario) ? (
                          <button
                            className="botao-icone botao-icone--perigo"
                            type="button"
                            onClick={() => excluir(funcionario)}
                            aria-label={`Excluir ${funcionario.nome}`}
                            title="Excluir funcionário"
                          >
                            <Icone nome="lixo" />
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {modalAberto ? (
        <Modal
          titulo={editando ? 'Editar usuário' : 'Novo funcionário'}
          aoFechar={fecharModal}
        >
          <p className="guia__ajuda">
            {editando
              ? 'Altere os dados de acesso deste usuário.'
              : 'O novo funcionário entra automaticamente na mesma empresa e usa o perfil Funcionário.'}
          </p>
          <form className="formulario" onSubmit={salvar}>
            <div className="campo">
              <label htmlFor="usuario-nome">Nome *</label>
              <input
                id="usuario-nome"
                type="text"
                maxLength={150}
                value={formulario.nome}
                onChange={(evento) => alterarCampo('nome', evento.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="campo">
              <label htmlFor="usuario-email">E-mail *</label>
              <input
                id="usuario-email"
                type="email"
                maxLength={254}
                value={formulario.email}
                onChange={(evento) => alterarCampo('email', evento.target.value)}
                required
              />
            </div>
            <div className="campo">
              <label htmlFor="usuario-telefone">Telefone</label>
              <input
                id="usuario-telefone"
                type="text"
                maxLength={20}
                placeholder="(81) 99999-9999"
                value={formulario.telefone}
                onChange={(evento) =>
                  alterarCampo('telefone', evento.target.value)
                }
              />
            </div>
            <div className="campo">
              <label htmlFor="usuario-senha">
                Senha {editando ? '' : '*'}
              </label>
              <input
                id="usuario-senha"
                type="password"
                autoComplete="new-password"
                minLength={editando ? undefined : 6}
                maxLength={128}
                placeholder={
                  editando ? 'Deixe em branco para manter a senha atual' : 'Mínimo 6 caracteres'
                }
                value={formulario.senha}
                onChange={(evento) => alterarCampo('senha', evento.target.value)}
                required={!editando}
              />
              {editando ? (
                <small>Preencha apenas se quiser trocar a senha.</small>
              ) : null}
            </div>

            {erroFormulario ? <Aviso>{erroFormulario}</Aviso> : null}

            <div className="acoes-formulario">
              <button
                className="botao botao--primario"
                type="submit"
                disabled={salvando}
              >
                {salvando
                  ? 'Salvando…'
                  : editando
                    ? 'Salvar alterações'
                    : 'Criar funcionário'}
              </button>
              <button
                className="botao botao--secundario"
                type="button"
                onClick={fecharModal}
                disabled={salvando}
              >
                Cancelar
              </button>
            </div>
          </form>
        </Modal>
      ) : null}
    </div>
  )
}
