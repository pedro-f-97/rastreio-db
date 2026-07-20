import client from './client'

const BASE = '/importacao'

export const previewExtrato = (perfilId, file) => {
    const form = new FormData()
    form.append('file', file)
    return client.post(`${BASE}/preview`, form, { params: { perfil_id: perfilId } })
}

export const importarExtrato = (perfilId, file) => {
    const form = new FormData()
    form.append('file', file)
    return client.post(`${BASE}/importar`, form, { params: { perfil_id: perfilId } })
}