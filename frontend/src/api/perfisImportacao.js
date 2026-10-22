import client from './client'
const BASE = '/perfis-importacao/'
export const listarPerfis = () => client.get(BASE)
export const criarPerfil = (dados) => client.post(BASE, dados)
// Sem barra no fim, como no router: com ela, o backend responde com um 307
export const atualizarPerfil = (id, dados) => client.put(`${BASE}${id}`, dados)
export const eliminarPerfil = (id) => client.delete(`${BASE}${id}`)
export const analisarFicheiro = (file) => {
    const form = new FormData()
    form.append('file', file)
    return client.post(`${BASE}analisar-ficheiro`, form)
}
export function associarContaPerfil(perfilId, contaId) {
    return client.patch(`${BASE}${perfilId}/conta`, { conta_id: contaId })
}