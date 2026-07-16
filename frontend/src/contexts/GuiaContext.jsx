import { createContext, useContext, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { marcarTourVisto } from '../api/configuracao'

const PASSOS = [
  {
    id: 'conta',
    rota: '/contas',
    dataTour: 'contas-nova-conta',
    texto: 'Começa por criar pelo menos uma conta bancária - é a base de tudo o resto. No caso do extrato não ter o histórico total da conta, indica o saldo que tinha numa data à escolha. Isto vai ser usado para calcular o saldo na conta no "Património". Se quiseres importar extratos de bancos diferentes, cria uma conta para cada um.',
  },
  {
    id: 'categoria',
    rota: '/categorias',
    dataTour: 'categorias-nova-categoria',
    texto: 'Aqui podes criar as categorias e subcategorias para as transações. Caso tenhas optado por as criar, as categorias predefinidas são um bom começo, mas podes ajustar conforme as tuas necessidades. Nas subcategorias, podes marcar como "Património" se quiseres que contem para o património.',
  },
  {
    id: 'perfil-importacao',
    rota: '/importacao',
    dataTour: 'importacao-novo-perfil',
    texto: 'Cria um perfil por banco — define como as colunas do extracto correspondem aos dados da aplicação.',
  },
  {
    id: 'importar-ficheiro',
    rota: '/importacao',
    dataTour: 'importacao-carregar-ficheiro',
    texto: 'Com um perfil pronto, já podes importar o extracto do banco. Se ainda não tiveres nenhum perfil, cria um primeiro.',
  },
{
    id: 'final',
    rota: '/sobre',
    dataTour: null,
    texto: 'Já tens o essencial configurado. Explora as Estatísticas, as Regras, ou revê estes conceitos a qualquer momento em "Sobre".',
  },
]

const GuiaContext = createContext(null)

export function GuiaProvider({ children }) {
  const [activo, setActivo] = useState(false)
  const [passoActual, setPassoActual] = useState(0)
  const navigate = useNavigate()

    function iniciar() {
      setPassoActual(0)
      setActivo(true)
      navigate(PASSOS[0].rota)
    }

  function avancar() {
    const ultimoPasso = passoActual === PASSOS.length - 1
    if (ultimoPasso) {
      setActivo(false)
      marcarTourVisto().catch(() => {})
      return
    }

    const passoSeguinte = PASSOS[passoActual + 1]
    if (passoSeguinte.rota !== PASSOS[passoActual].rota) {
      navigate(passoSeguinte.rota)
    }
    setPassoActual(passoActual + 1)
  }

  function sair() {
    setActivo(false)
    marcarTourVisto().catch(() => {})
  }

  function reiniciar() {
    setPassoActual(0)
    setActivo(true)
    navigate(PASSOS[0].rota)
  }

  const valor = {
    activo,
    passo: PASSOS[passoActual],
    passoActual,
    totalPassos: PASSOS.length,
    iniciar,
    avancar,
    sair,
    reiniciar,
  }

  return <GuiaContext.Provider value={valor}>{children}</GuiaContext.Provider>
}

export function useGuia() {
  const contexto = useContext(GuiaContext)
  if (!contexto) {
    throw new Error('useGuia tem de ser usado dentro de um GuiaProvider')
  }
  return contexto
}