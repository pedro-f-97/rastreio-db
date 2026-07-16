import api from './client'

export const getEstado = () => api.get('/configuracao/estado')
export const inicializar = (comCategorias = true, perfil = 'completo') =>
  api.post('/configuracao/inicializar', null, {
    params: { com_categorias: comCategorias, perfil },
  })
export const marcarTourVisto = () => api.post('/configuracao/tour-visto')