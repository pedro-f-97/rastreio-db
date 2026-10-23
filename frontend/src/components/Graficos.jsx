import { formatarEuros } from '../utils/formatacao';

// Peças comuns aos gráficos do recharts, para todos terem o mesmo aspecto

// A caixa que aparece ao passar o rato: o título e uma linha por série, com a
// cor da série. `formatar` recebe o valor e o item do recharts
export function TooltipGrafico({ active, payload, label, formatar = formatarEuros, titulo }) {
    if (!active || !payload?.length) return null;
    const linhas = payload.filter(p => p.value != null);
    if (linhas.length === 0) return null;
    return (
        <div className="grafico-tooltip">
            <div className="grafico-tooltip-titulo">{titulo ? titulo(payload[0].payload) : label}</div>
            {linhas.map(p => (
                <div key={p.dataKey} className="grafico-tooltip-linha">
                    <span className="grafico-tooltip-cor" style={{ background: p.color }} />
                    <span className="grafico-tooltip-nome">{p.name}</span>
                    <span className="grafico-tooltip-valor">{formatar(p.value, p)}</span>
                </div>
            ))}
        </div>
    );
}

// Um tick do eixo dos meses ("Mar 2025"): o mês, e o ano por baixo só em
// janeiro e no primeiro mês do gráfico, para o eixo não repetir o ano
export function TickMes({ x, y, payload, index }) {
    const [mes, ano] = String(payload.value).split(' ');
    return (
        <g transform={`translate(${x},${y})`}>
            <text dy={14} textAnchor="middle" fill="var(--text-secondary)" fontSize={11}>{mes}</text>
            {(mes === 'Jan' || index === 0) && (
                <text dy={29} textAnchor="middle" fill="var(--text-primary)" fontSize={11} fontFamily="var(--font-mono)">{ano}</text>
            )}
        </g>
    );
}
