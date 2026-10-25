import { useState, useEffect, useRef } from 'react'
import { listarPerfis, criarPerfil, atualizarPerfil, eliminarPerfil, analisarFicheiro } from '../api/perfisImportacao'
import { previewExtrato, importarExtrato, listarHistorico, desfazerImportacao } from '../api/importacao'
import { getContas } from '../api/contas'
import { classeValor, formatarEuros } from '../utils/formatacao'
import VerificacaoSaldo from '../components/VerificacaoSaldo'
import '../componentes.css'
import './Importacao.css'
import CabecalhoPagina from '../components/CabecalhoPagina'
import Icone from '../components/Icone'

const FORMATOS_DATA = [
    { label: '31/01/2026', valor: '%d/%m/%Y' },
    { label: '2026-01-31', valor: '%Y-%m-%d' },
    { label: '2026/01/31', valor: '%Y/%m/%d' },
    { label: '31-01-2026', valor: '%d-%m-%Y' },
]

const CAMPOS_COLUNA = [
    { chave: 'coluna_data', label: 'Coluna data' },
    { chave: 'coluna_descricao', label: 'Coluna descrição' },
    { chave: 'coluna_valor', label: 'Coluna valor', condicao: (f) => f.modo_valor === 'coluna_unica' },
    { chave: 'coluna_debito', label: 'Coluna débito', condicao: (f) => f.modo_valor === 'duas_colunas' },
    { chave: 'coluna_credito', label: 'Coluna crédito', condicao: (f) => f.modo_valor === 'duas_colunas' },
    { chave: 'coluna_saldo', label: 'Coluna saldo', condicao: (f) => f.tem_saldo },
    { chave: 'coluna_fee', label: 'Coluna fee', condicao: (f) => f.tem_fee },  
]

const PERFIL_VAZIO = {
    nome: '',
    tipo_ficheiro: 'xlsx',
    linha_inicio_dados: null,
    coluna_data: null,
    formato_data: '',
    coluna_descricao: null,
    modo_valor: 'coluna_unica',
    coluna_valor: null,
    coluna_debito: null,
    coluna_credito: null,
    separador_decimal: '.',
    tem_saldo: false,
    coluna_saldo: null,
    tem_fee: false,      
    coluna_fee: null,    
    conta_id: null,
}

function itemChecklist(label, preenchido) {
    return { label, preenchido }
}

export default function Importacao({ onDadosAlterados }) {
    const [perfis, setPerfis] = useState([])
    const [modalAberto, setModalAberto] = useState(false)
    // null ao criar; o id do perfil ao editar
    const [perfilEmEdicao, setPerfilEmEdicao] = useState(null)
    const [form, setForm] = useState(PERFIL_VAZIO)
    const [linhasAnalisadas, setLinhasAnalisadas] = useState(null)
    const [campoActivo, setCampoActivo] = useState(null)
    const [numColunas, setNumColunas] = useState(0)

    const [perfilId, setPerfilId] = useState('')
    const [ficheiro, setFicheiro] = useState(null)
    const [preview, setPreview] = useState(null)
    const [aImportar, setAImportar] = useState(false)
    const [resultado, setResultado] = useState(null)
    // A conta da última importação, cujo saldo se verifica, e um contador
    const [verificacao, setVerificacao] = useState({ contaId: null, chave: 0 })
    const inputFicheiroRef = useRef(null)

    const [contas, setContas] = useState([])
    const [historico, setHistorico] = useState([])

    useEffect(() => {
        carregar()
        carregarHistorico()
        getContas().then(res => setContas(res.data))
    }, [])

    async function carregar() {
        const res = await listarPerfis()
        setPerfis(res.data)
    }

    async function carregarHistorico() {
        const res = await listarHistorico()
        setHistorico(res.data)
    }

    function abrirModalNovo() {
        setPerfilEmEdicao(null)
        setForm(PERFIL_VAZIO)
        setLinhasAnalisadas(null)
        setCampoActivo(null)
        setNumColunas(0)
        setModalAberto(true)
    }

    function abrirModalEditar(perfil) {
        const { id, ...dados } = perfil
        setPerfilEmEdicao(id)
        setForm({ ...PERFIL_VAZIO, ...dados, tem_fee: dados.coluna_fee !== null })
        setLinhasAnalisadas(null)
        setCampoActivo(null)
        setNumColunas(0)
        setModalAberto(true)
    }

    function fecharModal() {
        setModalAberto(false)
        setCampoActivo(null)
        setLinhasAnalisadas(null)
    }

    function campo(nome, valor) {
        setForm(prev => ({ ...prev, [nome]: valor }))
    }

    async function aoAnalisarFicheiro(e) {
        const file = e.target.files[0]
        if (!file) return
        try {
            const res = await analisarFicheiro(file)
            setLinhasAnalisadas(res.data.linhas)
            const maxCols = Math.max(...res.data.linhas.map(l => l.length))
            setNumColunas(maxCols)
        } catch {
            alert('Erro ao ler ficheiro.')
        }
    }

    function aoClicarLinha(numeroLinha) {
        campo('linha_inicio_dados', numeroLinha)
    }

    function aoClicarCelula(indiceColuna) {
        if (!campoActivo) return
        campo(campoActivo, indiceColuna)
        setCampoActivo(null)
    }

    function labelColuna(indice) {
        if (indice === null || indice === undefined) return null
        return `Coluna ${indice}`
    }

    const camposVisiveis = CAMPOS_COLUNA.filter(c => !c.condicao || c.condicao(form))

    function calcularChecklist() {
        const items = [
            itemChecklist('Nome', !!form.nome.trim()),
            itemChecklist('Conta', form.conta_id !== null),
            itemChecklist('Início de dados', form.linha_inicio_dados !== null),
            itemChecklist('Coluna data', form.coluna_data !== null),
            itemChecklist('Coluna descrição', form.coluna_descricao !== null),
            itemChecklist('Formato data', !!form.formato_data),
        ]
        if (form.modo_valor === 'coluna_unica') {
            items.push(itemChecklist('Coluna valor', form.coluna_valor !== null))
        } else {
            items.push(itemChecklist('Coluna débito', form.coluna_debito !== null))
            items.push(itemChecklist('Coluna crédito', form.coluna_credito !== null))
        }
        if (form.tem_saldo) {
            items.push(itemChecklist('Coluna saldo', form.coluna_saldo !== null))
        }
        if (form.tem_fee) {
            items.push(itemChecklist('Coluna fee', form.coluna_fee !== null))
        }
        return items
    }

    async function aoGuardarPerfil() {
        const checklist = calcularChecklist()
        const emFalta = checklist.filter(i => !i.preenchido).map(i => i.label)
        if (emFalta.length > 0) {
            alert(`Falta preencher: ${emFalta.join(', ')}`)
            return
        }
        try {
            if (perfilEmEdicao) await atualizarPerfil(perfilEmEdicao, form)
            else await criarPerfil(form)
            fecharModal()
            carregar()
        } catch (err) {
            const detail = err.response?.data?.detail
            if (Array.isArray(detail)) {
                alert(detail.map(e => e.msg).join('\n'))
            } else {
                alert(detail || 'Erro ao guardar perfil.')
            }
        }
    }

    async function aoEliminarPerfil(id) {
        if (!confirm('Eliminar este perfil?')) return
        await eliminarPerfil(id)
        carregar()
    }

    async function aoCarregarFicheiro(e) {
        const file = e.target.files[0]
        if (!file) return
        setFicheiro(file)
        setPreview(null)
        setResultado(null)
        if (perfilId) await fazerPreview(file, perfilId)
    }

    async function aoSelecionarPerfil(e) {
        const id = e.target.value
        setPerfilId(id)
        setPreview(null)
        setResultado(null)
        if (id && ficheiro) await fazerPreview(ficheiro, id)
    }

    async function fazerPreview(file, pid) {
        try {
            const res = await previewExtrato(pid, file)
            setPreview(res.data)
        } catch (err) {
            alert(err.response?.data?.detail || 'Erro no preview.')
        }
    }

    async function aoImportar() {
        if (!perfilId || !ficheiro) return
        setAImportar(true)
        try {
            const res = await importarExtrato(perfilId, ficheiro)
            setResultado(res.data)
            const contaId = perfis.find(p => p.id === Number(perfilId))?.conta_id ?? null
            setVerificacao(v => ({ contaId, chave: v.chave + 1 }))
            setPreview(null)
            setFicheiro(null)
            if (inputFicheiroRef.current) inputFicheiroRef.current.value = ''
            carregarHistorico()
            onDadosAlterados?.()
        } catch (err) {
            alert(err.response?.data?.detail || 'Erro na importação.')
        } finally {
            setAImportar(false)
        }
    }

    async function aoDesfazer(imp) {
        const n = imp.inseridas
        if (!confirm(
            `Desfazer a importação de «${imp.ficheiro}» (${imp.conta_nome})?\n\n` +
            `${n === 1 ? 'Vai ser apagada 1 transação' : `Vão ser apagadas ${n} transações`}, ` +
            'com as categorias, subcategorias e notas que lhes deste.'
        )) return
        try {
            await desfazerImportacao(imp.id)
        } catch (err) {
            const detail = err.response?.data?.detail
            // 409 com movimentos: há transações já tratadas como ativos
            if (!detail?.movimentos) {
                alert(detail || 'Erro ao desfazer a importação.')
                return
            }
            const lista = detail.movimentos
                .map(m => `• ${m.ativo_nome}: ${m.tipo_movimento} de ${m.data}, ${formatarEuros(m.valor_total)}`)
                .join('\n')
            if (!confirm(
                `${detail.mensagem}\n\n${lista}\n\n` +
                'Apagar também estes movimentos? Se não, a importação fica como está.'
            )) return
            try {
                await desfazerImportacao(imp.id, true)
            } catch (err2) {
                alert(err2.response?.data?.detail || 'Erro ao desfazer a importação.')
                return
            }
        }
        setResultado(null)
        carregarHistorico()
        onDadosAlterados?.()
    }

    const checklist = calcularChecklist()

    return (
        <div className="pagina-container importacao-page">
            <CabecalhoPagina
                secao="01 · Transações"
                titulo="Importação"
                descricao="Escolhe o perfil do banco e o extracto: vês as linhas antes de importar, e as repetidas ficam de fora."
            />

            {/* SECÇÃO: IMPORTAR */}
            <section className="importacao-secao">
                <h2 className="titulo-secao"><span className="titulo-secao-numero">01</span>Importar extracto</h2>

                <div className="importacao-controles" data-tour="importacao-carregar-ficheiro">
                    <div className="importacao-passo">
                        <span className="importacao-passo-numero">1</span>
                        <div className="importacao-passo-corpo">
                            <span className="importacao-passo-titulo">Perfil do banco</span>
                            <select value={perfilId} onChange={aoSelecionarPerfil}>
                                <option value="">Selecionar perfil...</option>
                                {perfis.map(p => (
                                    <option key={p.id} value={p.id}>{p.nome}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <label className={`btn-ficheiro ${ficheiro ? 'com-ficheiro' : ''}`}>
                        <span className="importacao-passo-numero">2</span>
                        <Icone nome={ficheiro ? 'ficheiro' : 'carregar'} tamanho={22} />
                        <span className="btn-ficheiro-texto">
                            <span className="importacao-passo-titulo">{ficheiro ? 'Ficheiro escolhido' : 'Extracto'}</span>
                            <span className="btn-ficheiro-nome">{ficheiro ? ficheiro.name : 'Carregar ficheiro (.xlsx ou .csv)'}</span>
                        </span>
                        <input
                            ref={inputFicheiroRef}
                            type="file"
                            accept=".xlsx,.csv"
                            onChange={aoCarregarFicheiro}
                            hidden
                        />
                    </label>
                </div>

                {preview && (
                    <div className="importacao-preview">
                        <div className="importacao-preview-meta">
                            <span className="importacao-passo-numero">3</span>
                            <span>Total de linhas: <strong>{preview.total_linhas}</strong></span>
                            {preview.erros.length > 0 && (
                                <span className="importacao-erros-badge">
                                    {preview.erros.length} erro{preview.erros.length !== 1 ? 's' : ''}
                                </span>
                            )}
                        </div>

                        {preview.erros.length > 0 && (
                            <ul className="importacao-erros-lista">
                                {preview.erros.map((e, i) => (
                                    <li key={i}>Linha {e.linha}: {e.erro}</li>
                                ))}
                            </ul>
                        )}

                        <div className="tabela-wrapper">
                            <table className="tabela-base">
                                <thead>
                                    <tr>
                                        <th>Data</th>
                                        <th>Descrição</th>
                                        <th className="col-num">Valor</th>
                                        <th className="col-num">Saldo</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {preview.linhas_preview.map((t, i) => (
                                        <tr key={i}>
                                            <td className="col-data">{t.data}</td>
                                            <td>{t.descricao}</td>
                                            <td className={`col-num ${classeValor(t.valor)}`}>
                                                {formatarEuros(t.valor)}
                                            </td>
                                            <td className="col-num celula-secundaria">{formatarEuros(t.saldo)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                                {preview.total_linhas > preview.linhas_preview.length && (
                                    <tfoot>
                                        <tr>
                                            <td colSpan={4} className="preview-mais-linhas">
                                                + {preview.total_linhas - preview.linhas_preview.length} linhas não mostradas
                                            </td>
                                        </tr>
                                    </tfoot>
                                )}
                            </table>
                        </div>

                        <button
                            className="btn-primario btn-importar"
                            onClick={aoImportar}
                            disabled={aImportar}
                        >
                            <Icone nome="descarregar" /> {aImportar ? 'A importar...' : 'Importar'}
                        </button>
                    </div>
                )}

                {resultado && (
                    <div className="importacao-resultado">
                        <span className="resultado-inseridas"><Icone nome="confirmar" /> {resultado.inseridas} inseridas</span>
                        <span className="resultado-duplicadas">{resultado.duplicadas} duplicadas</span>
                    </div>
                )}

                {resultado && (
                    <VerificacaoSaldo
                        contaId={verificacao.contaId}
                        contaNome={contas.find(c => c.id === verificacao.contaId)?.nome}
                        chave={verificacao.chave}
                        onTransacaoCriada={t => {
                            onDadosAlterados?.()
                            setVerificacao(v => ({ contaId: t.conta_id, chave: v.chave + 1 }))
                        }}
                    />
                )}
            </section>

            {/* SECÇÃO: PERFIS */}
            <section className="importacao-secao">
                <div className="secao-cabecalho" data-tour="importacao-novo-perfil">
                    <h2 className="titulo-secao"><span className="titulo-secao-numero">02</span>Perfis de banco</h2>
                    <button className="btn-secundario" onClick={abrirModalNovo}><Icone nome="mais" /> Novo perfil</button>
                </div>

                {perfis.length === 0 ? (
                    <p className="estado-vazio">Nenhum perfil configurado.</p>
                ) : (
                    <div className="grelha-itens grelha-iguais grelha-perfis">
                        {perfis.map(p => (
                            <div key={p.id} className="item-lista perfil-cartao">
                                <div className="item-cabecalho item-cabecalho-limpo revelar-accoes">
                                    <div className="item-titulo">
                                        <span className="perfil-icone"><Icone nome="ficheiro" tamanho={16} /></span>
                                        <span className="item-nome" title={p.nome}>{p.nome}</span>
                                        <span className="chip chip-accent">
                                            {contas.find(c => c.id === p.conta_id)?.nome ?? '—'}
                                        </span>
                                    </div>
                                    <div className="accoes">
                                        <button onClick={() => abrirModalEditar(p)} title="Editar perfil"><Icone nome="editar" /></button>
                                        <button className="perigo" onClick={() => aoEliminarPerfil(p.id)} title="Eliminar perfil"><Icone nome="apagar" /></button>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            {/* SECÇÃO: HISTÓRICO */}
            <section className="importacao-secao">
                <h2 className="titulo-secao"><span className="titulo-secao-numero">03</span>Histórico de importações</h2>

                {historico.length === 0 ? (
                    <p className="estado-vazio">Nenhuma importação registada.</p>
                ) : (
                    <div className="tabela-wrapper">
                        <table className="tabela-base">
                            <thead>
                                <tr>
                                    <th>Data</th>
                                    <th>Conta</th>
                                    <th>Ficheiro</th>
                                    <th className="col-num">Inseridas</th>
                                    <th className="col-num">Duplicadas</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {historico.map(i => (
                                    <tr key={i.id}>
                                        <td className="col-data">{i.data_hora.slice(0, 16).replace('T', ' ')}</td>
                                        <td><span className="chip">{i.conta_nome}</span></td>
                                        <td className="importacao-ficheiro"><Icone nome="ficheiro" tamanho={14} /> {i.ficheiro}</td>
                                        <td className="col-num">{i.inseridas}</td>
                                        <td className="col-num celula-secundaria">{i.duplicadas}</td>
                                        <td className="col-accoes">
                                            {i.pode_desfazer && (
                                                <button
                                                    className="btn-ghost"
                                                    onClick={() => aoDesfazer(i)}
                                                    title="Só a importação mais recente de cada conta se pode desfazer"
                                                >
                                                    <Icone nome="desfazer" tamanho={14} /> Desfazer
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>

            {/* MODAL: PERFIL */}
            {modalAberto && (
                <div className="modal-overlay" onClick={fecharModal}>
                    <div className="modal modal-larga" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>{perfilEmEdicao ? 'Editar perfil' : 'Novo perfil'}</h3>
                            <button className="modal-fechar" onClick={fecharModal} title="Fechar"><Icone nome="fechar" /></button>
                        </div>

                        <div className="modal-corpo">
                            {/* Passo 1 */}
                            <div className="modal-passo">
                                <div className="modal-passo-titulo">1. Carrega um ficheiro exemplo</div>
                                {perfilEmEdicao && !linhasAnalisadas && (
                                    <div className="modal-passo-ajuda">
                                        Para mudar as colunas, carrega um ficheiro exemplo; sem ficheiro, ficam como estão.
                                    </div>
                                )}
                                <input className="input-ficheiro" type="file" accept=".xlsx,.csv" onChange={aoAnalisarFicheiro} />
                            </div>

                            {linhasAnalisadas && (
                                <>
                                    {/* Passo 2 */}
                                    <div className="modal-passo">
                                        <div className="modal-passo-titulo">
                                            2. Clica na primeira linha com valores reais
                                            <span className="modal-passo-ajuda"> (não a linha dos títulos das colunas)</span>
                                        </div>
                                        {form.linha_inicio_dados !== null && (
                                            <div className="modal-seleccao-activa">
                                                Início de dados: linha {form.linha_inicio_dados}
                                            </div>
                                        )}
                                        <div className="modal-tabela-wrapper">
                                            <table className="modal-tabela-analise">
                                                <thead>
                                                    <tr>
                                                        <th className="numero-linha"></th>
                                                        {Array.from({ length: numColunas }, (_, i) => (
                                                            <th key={i} className="numero-coluna">col {i}</th>
                                                        ))}
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {linhasAnalisadas.map((linha, i) => {
                                                        const numeroLinha = i + 1
                                                        const eInicio = form.linha_inicio_dados === numeroLinha
                                                        return (
                                                            <tr
                                                                key={i}
                                                                className={eInicio ? 'linha-inicio' : ''}
                                                                onClick={() => aoClicarLinha(numeroLinha)}
                                                            >
                                                                <td className="numero-linha">{numeroLinha}</td>
                                                                {Array.from({ length: numColunas }, (_, j) => (
                                                                    <td
                                                                        key={j}
                                                                        className={`celula-dados ${campoActivo ? 'celula-clicavel' : ''}`}
                                                                        onClick={e => {
                                                                            if (campoActivo) {
                                                                                e.stopPropagation()
                                                                                aoClicarCelula(j)
                                                                            }
                                                                        }}
                                                                    >
                                                                        {linha[j] ?? ''}
                                                                    </td>
                                                                ))}
                                                            </tr>
                                                        )
                                                    })}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>

                                    {/* Passo 3 */}
                                    <div className="modal-passo">
                                        <div className="modal-passo-titulo">
                                            3. Clica em cada campo e depois na coluna correspondente na tabela acima
                                        </div>
                                        <div className="modal-mapeamento">
                                            {camposVisiveis.map(({ chave, label }) => {
                                                const eActivo = campoActivo === chave
                                                const valorActual = form[chave]
                                                return (
                                                    <div
                                                        key={chave}
                                                        className={`modal-campo-coluna ${eActivo ? 'campo-activo' : ''} ${valorActual !== null ? 'campo-preenchido' : ''}`}
                                                        onClick={() => setCampoActivo(eActivo ? null : chave)}
                                                    >
                                                        <span className="campo-coluna-label">{label}</span>
                                                        <span className="campo-coluna-valor">
                                                            {valorActual !== null
                                                                ? labelColuna(valorActual)
                                                                : eActivo ? 'Clica numa coluna na tabela...' : 'Clica para seleccionar'
                                                            }
                                                        </span>
                                                    </div>
                                                )
                                            })}
                                        </div>
                                    </div>
                                </>
                            )}

                            {/* Passo 4 */}
                            <div className="modal-passo">
                                <div className="modal-passo-titulo">4. Configurações adicionais</div>
                                <div className="modal-grelha">
                                    <div className="modal-grupo">
                                        <label>Nome do perfil</label>
                                        <input value={form.nome} onChange={e => campo('nome', e.target.value)} placeholder="ex: CGD, BPI Conta Principal..." />
                                    </div>

                                    <div className="modal-grupo">
                                        <label>Tipo de ficheiro</label>
                                        <select value={form.tipo_ficheiro} onChange={e => campo('tipo_ficheiro', e.target.value)}>
                                            <option value="xlsx">XLSX</option>
                                            <option value="csv">CSV</option>
                                        </select>
                                    </div>

                                    <div className="modal-grupo">
                                        <label>Formato da data</label>
                                        <select value={form.formato_data} onChange={e => campo('formato_data', e.target.value)}>
                                            <option value="">Selecionar...</option>
                                            {FORMATOS_DATA.map(f => (
                                                <option key={f.valor} value={f.valor}>{f.label}</option>
                                            ))}
                                        </select>
                                    </div>

                                    <div className="modal-grupo">
                                        <label>Modo valor</label>
                                        <select value={form.modo_valor} onChange={e => campo('modo_valor', e.target.value)}>
                                            <option value="coluna_unica">Uma coluna (valores positivos e negativos)</option>
                                            <option value="duas_colunas">Duas colunas (débito e crédito separados)</option>
                                        </select>
                                    </div>

                                    <div className="modal-grupo">
                                        <label>Separador decimal</label>
                                        <select value={form.separador_decimal} onChange={e => campo('separador_decimal', e.target.value)}>
                                            <option value=".">Ponto — 1234.56</option>
                                            <option value=",">Vírgula — 1234,56</option>
                                        </select>
                                    </div>

                                    <div className="modal-grupo">
                                        <label>Conta bancária</label>
                                        <select value={form.conta_id ?? ''} onChange={e => campo('conta_id', e.target.value ? parseInt(e.target.value) : null)}>
                                            <option value="" disabled>Escolhe uma conta</option>
                                            {contas.map(c => (
                                                <option key={c.id} value={c.id}>{c.nome}</option>
                                            ))}
                                        </select>
                                    </div>

                                    <div className="modal-grupo modal-grupo-checkbox">
                                        <label>
                                            <input type="checkbox" checked={form.tem_saldo} onChange={e => campo('tem_saldo', e.target.checked)} />
                                            O ficheiro tem coluna de saldo
                                        </label>
                                    </div>
                                    <div className="modal-grupo modal-grupo-checkbox">
                                        <label>
                                            <input type="checkbox" checked={form.tem_fee} onChange={e => {
                                                campo('tem_fee', e.target.checked)
                                                if (!e.target.checked) campo('coluna_fee', null)
                                            }} />
                                            O ficheiro tem coluna de fee/comissão
                                        </label>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="modal-footer">
                            <div className="modal-checklist">
                                {checklist.map((item, i) => (
                                    <span key={i} className={`checklist-item ${item.preenchido ? 'checklist-ok' : 'checklist-falta'}`}>
                                        {item.preenchido ? '✓' : '✗'} {item.label}
                                    </span>
                                ))}
                            </div>
                            <div className="modal-footer-accoes">
                                <button className="btn-ghost" onClick={fecharModal}>Cancelar</button>
                                <button className="btn-primario" onClick={aoGuardarPerfil}>Guardar</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}