import { useState, useEffect } from 'react';
import { listarSubcategorias } from '../api/categorias';

export default function FiltrosTransacoes({ filtros, categorias, onChange }) {
    const anoActual = new Date().getFullYear();
    const anos = Array.from({ length: 5 }, (_, i) => anoActual - i);
    const meses = [
        { valor: 1, nome: 'Janeiro' }, { valor: 2, nome: 'Fevereiro' },
        { valor: 3, nome: 'Março' }, { valor: 4, nome: 'Abril' },
        { valor: 5, nome: 'Maio' }, { valor: 6, nome: 'Junho' },
        { valor: 7, nome: 'Julho' }, { valor: 8, nome: 'Agosto' },
        { valor: 9, nome: 'Setembro' }, { valor: 10, nome: 'Outubro' },
        { valor: 11, nome: 'Novembro' }, { valor: 12, nome: 'Dezembro' },
    ];

    const [subcategorias, setSubcategorias] = useState([]);

    useEffect(() => {
        if (filtros.categoria_id) {
            listarSubcategorias(filtros.categoria_id).then(res => setSubcategorias(res.data));
        } else {
            setSubcategorias([]);
            onChange({ subcategoria_id: null });
        }
    }, [filtros.categoria_id]);

    return (
        <div className="filtros">
            <select
                value={filtros.ano ?? ''}
                onChange={e => onChange({ ano: e.target.value ? Number(e.target.value) : null })}
            >
                <option value="">Todos os anos</option>
                {anos.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
            <select
                value={filtros.mes ?? ''}
                onChange={e => onChange({ mes: e.target.value ? Number(e.target.value) : null })}
            >
                <option value="">Todos os meses</option>
                {meses.map(m => <option key={m.valor} value={m.valor}>{m.nome}</option>)}
            </select>
            <select
                value={filtros.categoria_id ?? ''}
                onChange={e => onChange({ categoria_id: e.target.value ? Number(e.target.value) : null, subcategoria_id: null })}
            >
                <option value="">Todas as categorias</option>
                {categorias.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
            <select
                value={filtros.subcategoria_id ?? ''}
                onChange={e => onChange({ subcategoria_id: e.target.value ? Number(e.target.value) : null })}
                disabled={!filtros.categoria_id || subcategorias.length === 0}
            >
                <option value="">Todas as subcategorias</option>
                {subcategorias.map(s => <option key={s.id} value={s.id}>{s.nome}</option>)}
            </select>
            <select
                value={filtros.sinal ?? ''}
                onChange={e => onChange({ sinal: e.target.value || null })}
            >
                <option value="">Todos os valores</option>
                <option value="negativo">Negativos</option>
                <option value="positivo">Positivos</option>
            </select>
            <input
                type="text"
                placeholder="Pesquisar descrição..."
                value={filtros.descricao ?? ''}
                onChange={e => onChange({ descricao: e.target.value || null })}
            />
            <button
                className={filtros.por_categorizar ? 'btn-filtro-activo' : 'btn-filtro'}
                onClick={() => onChange({ por_categorizar: !filtros.por_categorizar, ano: null })}
            >
                {filtros.por_categorizar ? 'Mostrar todas' : 'Por categorizar'}
            </button>
        </div>
    );
}