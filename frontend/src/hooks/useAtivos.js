import { useState, useEffect, useCallback } from "react";
import { getAtivos, getResumoAtivo } from "../api/patrimonio";
import { listarTiposAtivo } from "../api/tiposAtivo";

export function useAtivos() {
  const [ativos, setAtivos] = useState([]);
  const [resumos, setResumos] = useState({});
  const [tiposAtivo, setTiposAtivo] = useState([]);
  const [loading, setLoading] = useState(true);

  const carregar = useCallback(async () => {
    setLoading(true);
    const [resAtivos, resTipos] = await Promise.all([
      getAtivos(),
      listarTiposAtivo(),
    ]);
    setAtivos(resAtivos.data);
    setTiposAtivo(resTipos.data);

    const resumosNovos = {};
    await Promise.all(
      resAtivos.data.map(async (a) => {
        const res = await getResumoAtivo(a.id);
        resumosNovos[a.id] = res.data;
      })
    );
    setResumos(resumosNovos);
    setLoading(false);
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  return { ativos, resumos, tiposAtivo, loading, recarregar: carregar };
}