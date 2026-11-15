import client from './client';

export function listarTiposAtivo() {
    return client.get('/tipos-ativo/');
}

export function criarTipoAtivo(nome, temUnidades = false, classificacaoFiscal = 'fora') {
    return client.post('/tipos-ativo/', {
        nome, tem_unidades: temUnidades, classificacao_fiscal: classificacaoFiscal,
    });
}

export function renomearTipoAtivo(id, nome, temUnidades, classificacaoFiscal) {
    return client.put(`/tipos-ativo/${id}`, {
        nome, tem_unidades: temUnidades, classificacao_fiscal: classificacaoFiscal,
    });
}

export function apagarTipoAtivo(id) {
    return client.delete(`/tipos-ativo/${id}`);
}