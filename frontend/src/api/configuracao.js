import api from './client'

export const getEstado = () => api.get('/configuracao/estado')
export const inicializar = (comCategorias = true) =>
  api.post('/configuracao/inicializar', null, { params: { com_categorias: comCategorias } })