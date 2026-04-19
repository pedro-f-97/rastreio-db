import client from './client';

export function listarCategorias() {
    return client.get('/categorias/');
}

export function listarSubcategorias(categoriaId) {
    return client.get(`/categorias/${categoriaId}/subcategorias/`);
}