import axios from 'axios'

const BASE = '/api/perfis-importacao'

export const listarPerfis = () => axios.get(BASE)
export const criarPerfil = (dados) => axios.post(BASE, dados)
export const atualizarPerfil = (id, dados) => axios.put(`${BASE}/${id}`, dados)
export const eliminarPerfil = (id) => axios.delete(`${BASE}/${id}`)
export const analisarFicheiro = (file) => {
    const form = new FormData()
    form.append('file', file)
    return axios.post(`${BASE}/analisar-ficheiro`, form)
}
export function associarContaPerfil(perfilId, contaId) {
    return axios.patch(`/api/perfis-importacao/${perfilId}/conta`, { conta_id: contaId })
}