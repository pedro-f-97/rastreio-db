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

export function transferenciasSemPar() {
    return client.get('/transacoes/transferencias-sem-par');
}

export function criarTransacao(dados) {
    return client.post('/transacoes/', dados);
}

export function apagarTransacao(id) {
    return client.delete(`/transacoes/${id}`);
}
