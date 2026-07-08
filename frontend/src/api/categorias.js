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

export function criarSubcategoria(categoriaId, nome, trataPatrimonio = false) {
    return client.post(`/categorias/${categoriaId}/subcategorias`, { nome, trata_patrimonio: trataPatrimonio });
}

export function renomearSubcategoria(categoriaId, subcategoriaId, nome, trataPatrimonio = null) {
    const payload = { nome };
    if (trataPatrimonio !== null) payload.trata_patrimonio = trataPatrimonio;
    return client.put(`/categorias/${categoriaId}/subcategorias/${subcategoriaId}`, payload);
}

export function apagarSubcategoria(categoriaId, subcategoriaId) {
    return client.delete(`/categorias/${categoriaId}/subcategorias/${subcategoriaId}`);
}