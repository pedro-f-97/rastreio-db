import client from './client';

export function listarRegras() {
    return client.get('/regras/');
}

export function criarRegra(dados) {
    return client.post('/regras/', dados);
}

export function apagarRegra(id) {
    return client.delete(`/regras/${id}`);
}

export function preVisualizarRegras() {
    return client.post('/regras/pre-visualizar');
}

export function aplicarEmMassa(ids) {
    return client.post('/regras/aplicar-em-massa', { ids });
}