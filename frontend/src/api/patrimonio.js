import client from "./client";

// --- PENDENTES ---
export const getPendentes = () => client.get("/patrimonio/pendentes");

// --- ATIVOS ---
export const getAtivos = () => client.get("/patrimonio/ativos");
export const criarAtivo = (payload) => client.post("/patrimonio/ativos", payload);
export const getResumoAtivo = (ativoId) => client.get(`/patrimonio/ativos/${ativoId}/resumo`);
export const eliminarAtivo = (id) => client.delete(`/patrimonio/ativos/${id}`);

// --- MOVIMENTOS ---
export const criarMovimento = (payload) => client.post("/patrimonio/movimentos", payload);
export const getMovimentos = (ativoId) => client.get(`/patrimonio/ativos/${ativoId}/movimentos`);
export const eliminarMovimento = (id) => client.delete(`/patrimonio/movimentos/${id}`);

// --- PREÇOS ---
export const registarPreco = (payload) => client.post("/patrimonio/precos", payload);