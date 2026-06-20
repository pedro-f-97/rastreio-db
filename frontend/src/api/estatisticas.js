import client from './client';

export function obterResumoMensal() {
    return client.get('/estatisticas/resumo-mensal');
}

export function obterPorCategoria(ano) {
    const params = ano && ano !== 'todos' ? `?ano=${ano}` : '';
    return client.get(`/estatisticas/por-categoria${params}`);
}

export function obterPorSubcategoria(ano) {
    const params = ano && ano !== 'todos' ? `?ano=${ano}` : '';
    return client.get(`/estatisticas/por-subcategoria${params}`);
}

export function obterDetalheMensal(ano, mes) {
    return client.get(`/estatisticas/detalhe-mensal?ano=${ano}&mes=${mes}`);
}
