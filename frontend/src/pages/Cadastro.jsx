/**
 * Cadastro em duas etapas:
 *   1) dados de acesso do usuário;
 *   2) dados da empresa.
 *
 * Os dois são enviados juntos em `POST /api/auth/cadastro`, que grava usuário
 * e empresa em uma única transação atômica no backend.
 */
import { useState } from 'react'
import { api, mensagemDeErro } from '../api'
import Marca from '../components/Marca'
import Tela from '../components/Tela'

const CAMPOS_USUARIO = ['nome', 'email', 'senha', 'telefone']
const CAMPOS_EMPRESA = [
  'razao_social',
  'cnpj',
  'cep',
  'inscricao',
  'telefone_empresa',
]

const somenteDigitos = (valor) => valor.replace(/\D/g, '')

function CampoErro({ mensagem }) {
  return mensagem ? <span className="campo__erro">{mensagem}</span> : null
}

export default function Cadastro({ aoFinalizar, aoIrLogin, aoVoltar }) {
  const [etapa, setEtapa] = useState(1)
  const [usuario, setUsuario] = useState({
    nome: '',
    email: '',
    telefone: '',
    senha: '',
    confirmar: '',
  })
  const [empresa, setEmpresa] = useState({
    razao_social: '',
    cnpj: '',
    cep: '',
    inscricao: '',
    telefone_empresa: '',
  })
  const [erros, setErros] = useState({})
  const [erroGeral, setErroGeral] = useState('')
  const [carregando, setCarregando] = useState(false)

  function atualizarUsuario(campo, valor) {
    setUsuario((atual) => ({ ...atual, [campo]: valor }))
    setErros((atuais) => ({ ...atuais, [campo]: undefined }))
  }

  function atualizarEmpresa(campo, valor) {
    setEmpresa((atual) => ({ ...atual, [campo]: valor }))
    setErros((atuais) => ({ ...atuais, [campo]: undefined }))
  }

  function validarUsuario() {
    const novos = {}
    if (!usuario.nome.trim()) novos.nome = 'Informe seu nome completo.'
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(usuario.email.trim())) {
      novos.email = 'Informe um e-mail válido.'
    }
    if (usuario.senha.length < 6) {
      novos.senha = 'A senha precisa ter pelo menos 6 caracteres.'
    }
    if (usuario.senha !== usuario.confirmar) {
      novos.confirmar = 'As senhas não conferem.'
    }
    setErros(novos)
    return Object.keys(novos).length === 0
  }

  function irParaEmpresa(evento) {
    evento.preventDefault()
    setErroGeral('')
    if (validarUsuario()) setEtapa(2)
  }

  async function finalizar(evento) {
    evento.preventDefault()
    setErroGeral('')

    const novos = {}
    if (!empresa.razao_social.trim()) {
      novos.razao_social = 'Informe a razão social da empresa.'
    }
    const cnpj = empresa.cnpj.replace(/[^0-9a-zA-Z]/g, '')
    if (cnpj.length !== 14) {
      novos.cnpj = 'O CNPJ deve ter 14 caracteres.'
    }
    if (empresa.cep && somenteDigitos(empresa.cep).length !== 8) {
      novos.cep = 'O CEP deve ter 8 dígitos.'
    }
    if (Object.keys(novos).length > 0) {
      setErros(novos)
      return
    }

    setCarregando(true)
    try {
      await api.cadastro(
        {
          razao_social: empresa.razao_social.trim(),
          cnpj,
          cep: somenteDigitos(empresa.cep) || null,
          inscricao: empresa.inscricao.trim() || null,
          telefone_empresa: empresa.telefone_empresa.trim() || null,
        },
        {
          nome: usuario.nome.trim(),
          email: usuario.email.trim(),
          senha: usuario.senha,
          telefone: usuario.telefone.trim() || null,
        },
      )

      try {
        const login = await api.login(usuario.email.trim(), usuario.senha)
        aoFinalizar(login.dados)
      } catch {
        aoIrLogin(
          'Conta e empresa criadas com sucesso! Entre com sua senha para continuar.',
        )
      }
    } catch (falha) {
      const campos = falha?.corpo?.campos || {}
      setErros(campos)
      if (Object.keys(campos).some((campo) => CAMPOS_EMPRESA.includes(campo))) {
        setEtapa(2)
      } else if (Object.keys(campos).some((campo) => CAMPOS_USUARIO.includes(campo))) {
        setEtapa(1)
      }
      setErroGeral(mensagemDeErro(falha))
    } finally {
      setCarregando(false)
    }
  }

  return (
    <Tela className="tela-cadastro">
      <header className="topo">
        <Marca />
      </header>

      <main className="centro">
        <section className="cartao cartao--largo" aria-labelledby="titulo-cadastro">
          <div className="cartao__cabecalho">
            <span className="hero__selo">NOVA CONTA</span>
            <h1 id="titulo-cadastro">
              {etapa === 1 ? 'Seus dados de acesso' : 'Dados da empresa'}
            </h1>
            <p>
              {etapa === 1
                ? 'Etapa 1 de 2 — o usuário é quem vai entrar no sistema.'
                : 'Etapa 2 de 2 — a empresa é o negócio vinculado ao usuário.'}
            </p>
            <p className="nota-etapa">
              Usuário e empresa são cadastros diferentes, mas são criados juntos:
              toda conta precisa de uma empresa vinculada.
            </p>
            <ol className="passos" aria-label="Etapas do cadastro">
              <li className={etapa === 1 ? 'ativo' : 'concluido'}>
                1 · Usuário
              </li>
              <li className={etapa === 2 ? 'ativo' : ''}>2 · Empresa</li>
            </ol>
          </div>

          {erroGeral ? <div className="alerta">{erroGeral}</div> : null}

          {etapa === 1 ? (
            <form className="formulario" onSubmit={irParaEmpresa} noValidate>
              <div className="grade">
                <div className="campo campo--largo">
                  <label htmlFor="cad-nome">Nome completo</label>
                  <input
                    id="cad-nome"
                    autoComplete="name"
                    placeholder="Maria Silva"
                    value={usuario.nome}
                    onChange={(evento) =>
                      atualizarUsuario('nome', evento.target.value)
                    }
                    autoFocus
                    required
                  />
                  <CampoErro mensagem={erros.nome} />
                </div>

                <div className="campo">
                  <label htmlFor="cad-email">E-mail</label>
                  <input
                    id="cad-email"
                    type="email"
                    autoComplete="email"
                    placeholder="maria@empresa.com"
                    value={usuario.email}
                    onChange={(evento) =>
                      atualizarUsuario('email', evento.target.value)
                    }
                    required
                  />
                  <CampoErro mensagem={erros.email} />
                </div>

                <div className="campo">
                  <label htmlFor="cad-telefone">Telefone (opcional)</label>
                  <input
                    id="cad-telefone"
                    autoComplete="tel"
                    placeholder="(81) 99999-0000"
                    maxLength={20}
                    value={usuario.telefone}
                    onChange={(evento) =>
                      atualizarUsuario('telefone', evento.target.value)
                    }
                  />
                  <CampoErro mensagem={erros.telefone} />
                </div>

                <div className="campo">
                  <label htmlFor="cad-senha">Senha</label>
                  <input
                    id="cad-senha"
                    type="password"
                    autoComplete="new-password"
                    placeholder="Mínimo 6 caracteres"
                    value={usuario.senha}
                    onChange={(evento) =>
                      atualizarUsuario('senha', evento.target.value)
                    }
                    required
                  />
                  <small>Mínimo de 6 caracteres.</small>
                  <CampoErro mensagem={erros.senha} />
                </div>

                <div className="campo">
                  <label htmlFor="cad-confirmar">Confirmar senha</label>
                  <input
                    id="cad-confirmar"
                    type="password"
                    autoComplete="new-password"
                    placeholder="Repita a senha"
                    value={usuario.confirmar}
                    onChange={(evento) =>
                      atualizarUsuario('confirmar', evento.target.value)
                    }
                    required
                  />
                  <CampoErro mensagem={erros.confirmar} />
                </div>
              </div>

              <div className="acoes-formulario">
                <button className="botao botao--primario" type="submit">
                  Continuar para empresa
                </button>
                <button
                  className="botao botao--texto"
                  type="button"
                  onClick={aoIrLogin}
                >
                  Já tenho conta
                </button>
              </div>
            </form>
          ) : (
            <form className="formulario" onSubmit={finalizar} noValidate>
              <div className="grade">
                <div className="campo campo--largo">
                  <label htmlFor="cad-razao">Razão social</label>
                  <input
                    id="cad-razao"
                    placeholder="Byte Estoque Ltda"
                    value={empresa.razao_social}
                    onChange={(evento) =>
                      atualizarEmpresa('razao_social', evento.target.value)
                    }
                    autoFocus
                    required
                  />
                  <CampoErro mensagem={erros.razao_social} />
                </div>

                <div className="campo">
                  <label htmlFor="cad-cnpj">CNPJ</label>
                  <input
                    id="cad-cnpj"
                    placeholder="00.000.000/0000-00"
                    maxLength={18}
                    value={empresa.cnpj}
                    onChange={(evento) =>
                      atualizarEmpresa('cnpj', evento.target.value)
                    }
                    required
                  />
                  <small>Aceita máscara e CNPJ alfanumérico.</small>
                  <CampoErro mensagem={erros.cnpj} />
                </div>

                <div className="campo">
                  <label htmlFor="cad-cep">CEP (opcional)</label>
                  <input
                    id="cad-cep"
                    placeholder="50030-230"
                    maxLength={9}
                    value={empresa.cep}
                    onChange={(evento) =>
                      atualizarEmpresa('cep', evento.target.value)
                    }
                  />
                  <CampoErro mensagem={erros.cep} />
                </div>

                <div className="campo">
                  <label htmlFor="cad-inscricao">Inscrição (opcional)</label>
                  <input
                    id="cad-inscricao"
                    placeholder="IE-0012345-67"
                    maxLength={30}
                    value={empresa.inscricao}
                    onChange={(evento) =>
                      atualizarEmpresa('inscricao', evento.target.value)
                    }
                  />
                  <CampoErro mensagem={erros.inscricao} />
                </div>

                <div className="campo">
                  <label htmlFor="cad-telefone-empresa">
                    Telefone da empresa (opcional)
                  </label>
                  <input
                    id="cad-telefone-empresa"
                    placeholder="(81) 3221-4455"
                    maxLength={20}
                    value={empresa.telefone_empresa}
                    onChange={(evento) =>
                      atualizarEmpresa('telefone_empresa', evento.target.value)
                    }
                  />
                  <CampoErro mensagem={erros.telefone_empresa} />
                </div>
              </div>

              <div className="acoes-formulario">
                <button
                  className="botao botao--secundario"
                  type="button"
                  onClick={() => {
                    setErros({})
                    setErroGeral('')
                    setEtapa(1)
                  }}
                >
                  Voltar
                </button>
                <button
                  className="botao botao--primario"
                  type="submit"
                  disabled={carregando}
                >
                  {carregando ? 'Criando conta e empresa...' : 'Criar conta e empresa'}
                </button>
              </div>
            </form>
          )}

          <div className="rodape-formulario">
            <button className="botao botao--texto" type="button" onClick={aoVoltar}>
              ← Voltar para o início
            </button>
          </div>
        </section>
      </main>
    </Tela>
  )
}
