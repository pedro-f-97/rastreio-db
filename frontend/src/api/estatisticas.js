import client from './client';

export function obterResumoMensal() {
    return client.get('/estatisticas/resumo-mensal');
}

export function obterPorCategoria() {
    return client.get('/estatisticas/por-categoria');
}

export function obterPorSubcategoria() {
    return client.get('/estatisticas/por-subcategoria');
}

export function obterDetalheMensal(ano, mes) {
    return client.get(`/estatisticas/detalhe-mensal?ano=${ano}&mes=${mes}`);
}