import axios from 'axios'

const BASE = '/api/importacao'

export const previewExtrato = (perfilId, file) => {
    const form = new FormData()
    form.append('file', file)
    return axios.post(`${BASE}/preview`, form, { params: { perfil_id: perfilId } })
}

export const importarExtrato = (perfilId, file) => {
    const form = new FormData()
    form.append('file', file)
    return axios.post(`${BASE}/importar`, form, { params: { perfil_id: perfilId } })
}