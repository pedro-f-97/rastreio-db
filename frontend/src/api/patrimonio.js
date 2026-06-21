import client from "./client";

// --- PENDENTES ---
export const getPendentes = () => client.get("/patrimonio/pendentes");

// --- ATIVOS ---
export const getAtivos = () => client.get("/patrimonio/ativos");
export const criarAtivo = (payload) => client.post("/patrimonio/ativos", payload);

// --- MOVIMENTOS ---
export const criarMovimento = (payload) => client.post("/patrimonio/movimentos", payload);
export const getMovimentos = (ativoId) => client.get(`/patrimonio/ativos/${ativoId}/movimentos`);

// --- PREÇOS ---
export const registarPreco = (payload) => client.post("/patrimonio/precos", payload);