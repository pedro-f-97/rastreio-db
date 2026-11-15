import client from './client';

export function obterAnosIrs() {
    return client.get('/irs/anos');
}

export function obterRelatorioIrs(ano) {
    return client.get(`/irs/${ano}`);
}

// `tabela`: vendas, dividendos ou juros
export function descarregarCsvIrs(ano, tabela) {
    return client.get(`/irs/${ano}/csv`, { params: { tabela }, responseType: 'blob' });
}
