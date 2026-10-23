import client from "./client";

// --- PENDENTES ---
export const getPendentes = () => client.get("/patrimonio/pendentes");

// --- ATIVOS ---
export const getAtivos = () => client.get("/patrimonio/ativos");
export const criarAtivo = (payload) => client.post("/patrimonio/ativos", payload);
export const getResumoAtivo = (ativoId) => client.get(`/patrimonio/ativos/${ativoId}/resumo`);
export const eliminarAtivo = (id) => client.delete(`/patrimonio/ativos/${id}`);
export const editarAtivo = (id, payload) => client.put(`/patrimonio/ativos/${id}`, payload);

// --- MOVIMENTOS ---
export const criarMovimento = (payload) => client.post("/patrimonio/movimentos", payload);
export const getMovimentos = (ativoId) => client.get(`/patrimonio/ativos/${ativoId}/movimentos`);
export const eliminarMovimento = (id) => client.delete(`/patrimonio/movimentos/${id}`);

// --- PREÇOS ---
export const registarPreco = (payload) => client.post("/patrimonio/precos", payload);
export const getPrecos = (ativoId) => client.get(`/patrimonio/ativos/${ativoId}/precos`);
export const eliminarPreco = (id) => client.delete(`/patrimonio/precos/${id}`);

// --- EVOLUÇÃO ---
export const obterEvolucao = (dataInicio, dataFim) =>
    client.get("/patrimonio/evolucao", { params: { data_inicio: dataInicio, data_fim: dataFim } });

// --- CRESCIMENTO ---
// `ano` null = todos os meses
export const obterCrescimento = (ano) =>
    client.get("/patrimonio/crescimento", { params: { ano: ano ?? undefined } });
