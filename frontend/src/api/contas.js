import client from "./client";

export const getContas = () => client.get("/contas/");
export const criarConta = (payload) => client.post("/contas/", payload);
export const actualizarConta = (id, payload) => client.put(`/contas/${id}`, payload);
export const apagarConta = (id) => client.delete(`/contas/${id}`);
export const getSaldoConta = (id) => client.get(`/contas/${id}/saldo`);