// O estilo comum dos eixos dos gráficos: sem linha nem traços, só os números
export const EIXO = {
  axisLine: false,
  tickLine: false,
  tick: { fill: 'var(--text-secondary)', fontSize: 11, fontFamily: 'var(--font-mono)' },
};

// A grelha: só as linhas horizontais, a tracejado fino
export const GRELHA = {
  stroke: 'var(--border)',
  strokeDasharray: '2 4',
  vertical: false,
};

// A paleta das categorias, pela ordem em que se atribui
export const PALETA = Array.from({ length: 10 }, (_, i) => `var(--chart-${i + 1})`);
