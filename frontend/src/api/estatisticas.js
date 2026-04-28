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