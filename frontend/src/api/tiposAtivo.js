import client from './client';

export function listarTiposAtivo() {
    return client.get('/tipos-ativo/');
}

export function criarTipoAtivo(nome, temUnidades = false) {
    return client.post('/tipos-ativo/', { nome, tem_unidades: temUnidades });
}

export function renomearTipoAtivo(id, nome, temUnidades) {
    return client.put(`/tipos-ativo/${id}`, { nome, tem_unidades: temUnidades });
}

export function apagarTipoAtivo(id) {
    return client.delete(`/tipos-ativo/${id}`);
}