import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.DEV ? 'http://localhost:9742/api' : '/api',
})

// Um erro da API que nenhuma página apanhou ficava em silêncio.
// Só os pedidos sem `catch` chegam aqui: os que a página já trata não se
// mostram duas vezes.
window.addEventListener('unhandledrejection', (evento) => {
  const erro = evento.reason
  if (!axios.isAxiosError(erro)) return
  const detalhe = erro.response?.data?.detail
  const texto = Array.isArray(detalhe)
    ? detalhe.map(d => d.msg).join('\n')
    : detalhe || 'Não foi possível comunicar com o servidor.'
  alert(`Erro: ${texto}`)
})

export default api
