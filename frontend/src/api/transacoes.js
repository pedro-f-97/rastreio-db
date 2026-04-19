import client from './client';

export function listarTransacoes(params) {
    return client.get('/transacoes/', { params });
}

export function atualizarTransacao(id, dados) {
    return client.put(`/transacoes/${id}`, dados);
}

export function importarExtrato(ficheiro) {
    const formData = new FormData();
    formData.append('file', ficheiro);
    return client.post('/importacao/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    });
}