import api from './client'

export const getEstado = () => api.get('/configuracao/estado')
export const inicializar = () => api.post('/configuracao/inicializar')