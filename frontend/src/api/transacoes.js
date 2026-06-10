import client from './client';

export function listarTransacoes(params) {
    return client.get('/transacoes/', { params });
}

export function atualizarTransacao(id, dados) {
    return client.put(`/transacoes/${id}`, dados);
}

export function totalPorCategorizar() {
    return client.get('/transacoes/por-categorizar/total');
}