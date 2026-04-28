import api from './client';

export const exportarBackup = () => {
    // Para downloads, o ideal é abrir numa nova aba ou usar window.location
    window.location.href = `${api.defaults.baseURL}/backups/exportar`;
};

export const importarBackup = (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/backups/importar', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    });
};