import client from './client';

export function listarCategorias() {
    return client.get('/categorias/');
}

export function listarSubcategorias(categoriaId) {
    return client.get(`/categorias/${categoriaId}/subcategorias`);
}

export function criarCategoria(nome, tipo) {
    return client.post('/categorias/', { nome, tipo });
}

export function renomearCategoria(id, nome, tipo) {
    return client.put(`/categorias/${id}`, { nome, tipo });
}

export function apagarCategoria(id) {
    return client.delete(`/categorias/${id}`);
}

// `classeDespesa` só se envia nas categorias de despesa: null é sem
// classificação, e undefined não a envia
export function criarSubcategoria(categoriaId, nome, trataPatrimonio = false, classeDespesa = undefined) {
    const payload = { nome, trata_patrimonio: trataPatrimonio };
    if (classeDespesa !== undefined) payload.classe_despesa = classeDespesa;
    return client.post(`/categorias/${categoriaId}/subcategorias`, payload);
}

// Na edição, `classeDespesa` undefined mantém a classificação, e null tira-a
export function renomearSubcategoria(categoriaId, subcategoriaId, nome, trataPatrimonio = null, classeDespesa = undefined) {
    const payload = { nome };
    if (trataPatrimonio !== null) payload.trata_patrimonio = trataPatrimonio;
    if (classeDespesa !== undefined) payload.classe_despesa = classeDespesa;
    return client.put(`/categorias/${categoriaId}/subcategorias/${subcategoriaId}`, payload);
}

export function apagarSubcategoria(categoriaId, subcategoriaId) {
    return client.delete(`/categorias/${categoriaId}/subcategorias/${subcategoriaId}`);
}