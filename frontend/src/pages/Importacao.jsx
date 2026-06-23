import { useState, useEffect, useRef } from 'react'
import { listarPerfis, criarPerfil, eliminarPerfil, analisarFicheiro, associarContaPerfil } from '../api/perfisImportacao'
import { previewExtrato, importarExtrato } from '../api/importacao'
import { getContas } from '../api/contas'
import './Importacao.css'

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
    conta_id: null,
}

function itemChecklist(label, preenchido) {
    return { label, preenchido }
}

export default function Importacao() {
    const [perfis, setPerfis] = useState([])
    const [modalAberto, setModalAberto] = useState(false)
    const [form, setForm] = useState(PERFIL_VAZIO)
    const [linhasAnalisadas, setLinhasAnalisadas] = useState(null)
    const [campoActivo, setCampoActivo] = useState(null)
    const [numColunas, setNumColunas] = useState(0)

    const [perfilId, setPerfilId] = useState('')
    const [ficheiro, setFicheiro] = useState(null)
    const [preview, setPreview] = useState(null)
    const [aImportar, setAImportar] = useState(false)
    const [resultado, setResultado] = useState(null)
    const inputFicheiroRef = useRef(null)

    const [contas, setContas] = useState([])

    useEffect(() => {
        carregar()
        getContas().then(res => setContas(res.data))
    }, [])

    async function carregar() {
        const res = await listarPerfis()
        setPerfis(res.data)
    }

    function abrirModalNovo() {
        setForm(PERFIL_VAZIO)
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
            await criarPerfil(form)
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
            setPreview(null)
            setFicheiro(null)
            if (inputFicheiroRef.current) inputFicheiroRef.current.value = ''
        } catch (err) {
            alert(err.response?.data?.detail || 'Erro na importação.')
        } finally {
            setAImportar(false)
        }
    }

    const checklist = calcularChecklist()

    return (
        <div className="importacao-page">
            {/* SECÇÃO: PERFIS */}
            <section className="importacao-secao">
                <div className="importacao-secao-header">
                    <h2>Perfis de banco</h2>
                    <button onClick={abrirModalNovo}>+ Novo perfil</button>
                </div>

                {perfis.length === 0 ? (
                    <p className="importacao-vazio">Nenhum perfil configurado.</p>
                ) : (
                    <table className="importacao-tabela">
                        <thead>
                            <tr>
                                <th>Nome</th>
                                <th>Ficheiro</th>
                                <th>Modo valor</th>
                                <th>Início dados</th>
                                <th>Conta</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {perfis.map(p => (
                                <tr key={p.id}>
                                    <td>{p.nome}</td>
                                    <td>{p.tipo_ficheiro}</td>
                                    <td>{p.modo_valor}</td>
                                    <td>linha {p.linha_inicio_dados}</td>
                                    <td>
                                    <td>{contas.find(c => c.id === p.conta_id)?.nome ?? '—'}</td>
                                    </td>
                                    <td className="importacao-accoes">
                                        <button className="btn-perigo" onClick={() => aoEliminarPerfil(p.id)}>🗑</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </section>

            {/* SECÇÃO: IMPORTAR */}
            <section className="importacao-secao">
                <div className="importacao-secao-header">
                    <h2>Importar extrato</h2>
                </div>

                <div className="importacao-controles">
                    <select value={perfilId} onChange={aoSelecionarPerfil}>
                        <option value="">Selecionar perfil...</option>
                        {perfis.map(p => (
                            <option key={p.id} value={p.id}>{p.nome}</option>
                        ))}
                    </select>

                    <label className="btn-ficheiro">
                        {ficheiro ? ficheiro.name : 'Carregar ficheiro'}
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

                        <table className="importacao-tabela">
                            <thead>
                                <tr>
                                    <th>Data</th>
                                    <th>Descrição</th>
                                    <th>Valor</th>
                                    <th>Saldo</th>
                                </tr>
                            </thead>
                            <tbody>
                                {preview.linhas_preview.map((t, i) => (
                                    <tr key={i}>
                                        <td>{t.data}</td>
                                        <td>{t.descricao}</td>
                                        <td className={t.valor < 0 ? 'valor-negativo' : 'valor-positivo'}>
                                            {t.valor.toFixed(2)}
                                        </td>
                                        <td>{t.saldo != null ? t.saldo.toFixed(2) : '—'}</td>
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

                        <button
                            className="btn-importar"
                            onClick={aoImportar}
                            disabled={aImportar}
                        >
                            {aImportar ? 'A importar...' : 'Importar'}
                        </button>
                    </div>
                )}

                {resultado && (
                    <div className="importacao-resultado">
                        <span className="resultado-inseridas">✓ {resultado.inseridas} inseridas</span>
                        <span className="resultado-duplicadas">{resultado.duplicadas} duplicadas</span>
                    </div>
                )}
            </section>

            {/* MODAL: PERFIL */}
            {modalAberto && (
                <div className="modal-overlay" onClick={fecharModal}>
                    <div className="modal modal-perfil" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>Novo perfil</h3>
                            <button className="modal-fechar" onClick={fecharModal}>✕</button>
                        </div>

                        <div className="modal-corpo">
                            {/* Passo 1 */}
                            <div className="modal-passo">
                                <div className="modal-passo-titulo">1. Carrega um ficheiro exemplo</div>
                                <input type="file" accept=".xlsx,.csv" onChange={aoAnalisarFicheiro} />
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

                                    <div className="modal-grupo modal-grupo-checkbox">
                                        <label>
                                            <input type="checkbox" checked={form.tem_saldo} onChange={e => campo('tem_saldo', e.target.checked)} />
                                            O ficheiro tem coluna de saldo
                                        </label>
                                    </div>
                                    <div className="modal-grupo">
                                        <label>Conta bancária</label>
                                        <select value={form.conta_id ?? ''} onChange={e => campo('conta_id', e.target.value ? parseInt(e.target.value) : null)}>
                                            <option value="">Sem conta</option>
                                            {contas.map(c => (
                                                <option key={c.id} value={c.id}>{c.nome}</option>
                                            ))}
                                        </select>
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
                                <button onClick={fecharModal}>Cancelar</button>
                                <button className="btn-primario" onClick={aoGuardarPerfil}>Guardar</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
