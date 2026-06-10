import { useState, useEffect, useRef } from 'react'
import { listarPerfis, criarPerfil, atualizarPerfil, eliminarPerfil, analisarFicheiro } from '../api/perfisImportacao'
import { previewExtrato, importarExtrato } from '../api/importacao'
import './Importacao.css'

const PERFIL_VAZIO = {
    nome: '',
    tipo_ficheiro: 'xlsx',
    linha_inicio_dados: 1,
    coluna_data: 0,
    formato_data: '%d/%m/%Y',
    coluna_descricao: 1,
    modo_valor: 'coluna_unica',
    coluna_valor: 2,
    coluna_debito: null,
    coluna_credito: null,
    separador_decimal: '.',
    tem_saldo: false,
    coluna_saldo: null,
}

export default function Importacao() {
    const [perfis, setPerfis] = useState([])
    const [modalAberto, setModalAberto] = useState(false)
    const [perfilEmEdicao, setPerfilEmEdicao] = useState(null) // null = novo
    const [form, setForm] = useState(PERFIL_VAZIO)
    const [linhasAnalisadas, setLinhasAnalisadas] = useState(null)

    // Importação
    const [perfilId, setPerfilId] = useState('')
    const [ficheiro, setFicheiro] = useState(null)
    const [preview, setPreview] = useState(null)
    const [aImportar, setAImportar] = useState(false)
    const [resultado, setResultado] = useState(null)
    const inputFicheiroRef = useRef(null)

    useEffect(() => { carregar() }, [])

    async function carregar() {
        const res = await listarPerfis()
        setPerfis(Array.isArray(res.data) ? res.data : [])
        console.log(res.data)
    }

    function abrirModalNovo() {
        setPerfilEmEdicao(null)
        setForm(PERFIL_VAZIO)
        setLinhasAnalisadas(null)
        setModalAberto(true)
    }

    function abrirModalEditar(perfil) {
        setPerfilEmEdicao(perfil)
        setForm({ ...perfil })
        setLinhasAnalisadas(null)
        setModalAberto(true)
    }

    function fecharModal() {
        setModalAberto(false)
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
        } catch {
            alert('Erro ao ler ficheiro.')
        }
    }

    async function aoGuardarPerfil() {
        if (!form.nome.trim()) { alert('Nome obrigatório.'); return }
        try {
            if (perfilEmEdicao) {
                await atualizarPerfil(perfilEmEdicao.id, form)
            } else {
                await criarPerfil(form)
            }
            fecharModal()
            carregar()
        } catch (err) {
            alert(err.response?.data?.detail || 'Erro ao guardar perfil.')
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
                                    <td className="importacao-accoes">
                                        <button onClick={() => abrirModalEditar(p)}>✏️</button>
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
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>{perfilEmEdicao ? 'Editar perfil' : 'Novo perfil'}</h3>
                            <button className="modal-fechar" onClick={fecharModal}>✕</button>
                        </div>

                        <div className="modal-corpo">
                            {/* Análise de ficheiro */}
                            <div className="modal-grupo">
                                <label>Ficheiro exemplo (para identificar colunas)</label>
                                <input type="file" accept=".xlsx,.csv" onChange={aoAnalisarFicheiro} />
                            </div>

                            {linhasAnalisadas && (
                                <div className="modal-preview-ficheiro">
                                    <table>
                                        <thead>
                                            <tr>
                                                {linhasAnalisadas[0]?.map((_, i) => (
                                                    <th key={i}>col {i}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {linhasAnalisadas.map((linha, i) => (
                                                <tr key={i}>
                                                    {linha.map((cel, j) => (
                                                        <td key={j}>{cel}</td>
                                                    ))}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}

                            <div className="modal-grelha">
                                <div className="modal-grupo">
                                    <label>Nome do perfil</label>
                                    <input value={form.nome} onChange={e => campo('nome', e.target.value)} />
                                </div>

                                <div className="modal-grupo">
                                    <label>Tipo de ficheiro</label>
                                    <select value={form.tipo_ficheiro} onChange={e => campo('tipo_ficheiro', e.target.value)}>
                                        <option value="xlsx">XLSX</option>
                                        <option value="csv">CSV</option>
                                    </select>
                                </div>

                                <div className="modal-grupo">
                                    <label>Linha início de dados</label>
                                    <input type="number" min="1" value={form.linha_inicio_dados} onChange={e => campo('linha_inicio_dados', parseInt(e.target.value))} />
                                </div>

                                <div className="modal-grupo">
                                    <label>Coluna data (índice)</label>
                                    <input type="number" min="0" value={form.coluna_data} onChange={e => campo('coluna_data', parseInt(e.target.value))} />
                                </div>

                                <div className="modal-grupo">
                                    <label>Formato data</label>
                                    <input value={form.formato_data} onChange={e => campo('formato_data', e.target.value)} placeholder="%d/%m/%Y" />
                                </div>

                                <div className="modal-grupo">
                                    <label>Coluna descrição (índice)</label>
                                    <input type="number" min="0" value={form.coluna_descricao} onChange={e => campo('coluna_descricao', parseInt(e.target.value))} />
                                </div>

                                <div className="modal-grupo">
                                    <label>Modo valor</label>
                                    <select value={form.modo_valor} onChange={e => campo('modo_valor', e.target.value)}>
                                        <option value="coluna_unica">Coluna única</option>
                                        <option value="duas_colunas">Duas colunas (débito/crédito)</option>
                                    </select>
                                </div>

                                {form.modo_valor === 'coluna_unica' ? (
                                    <div className="modal-grupo">
                                        <label>Coluna valor (índice)</label>
                                        <input type="number" min="0" value={form.coluna_valor ?? ''} onChange={e => campo('coluna_valor', parseInt(e.target.value))} />
                                    </div>
                                ) : (
                                    <>
                                        <div className="modal-grupo">
                                            <label>Coluna débito (índice)</label>
                                            <input type="number" min="0" value={form.coluna_debito ?? ''} onChange={e => campo('coluna_debito', parseInt(e.target.value))} />
                                        </div>
                                        <div className="modal-grupo">
                                            <label>Coluna crédito (índice)</label>
                                            <input type="number" min="0" value={form.coluna_credito ?? ''} onChange={e => campo('coluna_credito', parseInt(e.target.value))} />
                                        </div>
                                    </>
                                )}

                                <div className="modal-grupo">
                                    <label>Separador decimal</label>
                                    <select value={form.separador_decimal} onChange={e => campo('separador_decimal', e.target.value)}>
                                        <option value=".">Ponto (.)</option>
                                        <option value=",">Vírgula (,)</option>
                                    </select>
                                </div>

                                <div className="modal-grupo modal-grupo-checkbox">
                                    <label>
                                        <input type="checkbox" checked={form.tem_saldo} onChange={e => campo('tem_saldo', e.target.checked)} />
                                        Tem coluna de saldo
                                    </label>
                                </div>

                                {form.tem_saldo && (
                                    <div className="modal-grupo">
                                        <label>Coluna saldo (índice)</label>
                                        <input type="number" min="0" value={form.coluna_saldo ?? ''} onChange={e => campo('coluna_saldo', parseInt(e.target.value))} />
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="modal-footer">
                            <button onClick={fecharModal}>Cancelar</button>
                            <button className="btn-primario" onClick={aoGuardarPerfil}>Guardar</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}