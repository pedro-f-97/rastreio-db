const formatadorMonetario = new Intl.NumberFormat('pt-PT', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  useGrouping: true,
});

/**
 * Formata um número como valor monetário em euros. 
 * O formato toLocaleString('pt-PT') não separava corretamente os milhares.
 * Ex: 5233.75 → "5 233,75 €"
 */
export function formatarEuros(valor) {
  if (valor == null) return "—";
  return formatadorMonetario.format(valor) + " €";
}

const formatadorPercentagem = new Intl.NumberFormat('pt-PT', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  useGrouping: true,
});

/**
 * Formata uma percentagem com uma casa decimal, com vírgula.
 * Ex: 44.85 → "44,9%"
 */
export function formatarPercentagem(valor) {
  if (valor == null) return "—";
  return formatadorPercentagem.format(valor) + "%";
}

const formatadorEixo = new Intl.NumberFormat('pt-PT', {
  maximumFractionDigits: 0,
  useGrouping: true,
});

/**
 * Formata os valores dos eixos dos gráficos: euros sem cêntimos, com os
 * milhares separados. Ex: 12000 → "12 000 €"
 */
export function formatarEurosEixo(valor) {
  return formatadorEixo.format(valor) + " €";
}

const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

/**
 * Nome curto de um mês, para os eixos e as tabelas. Ex: (2025, 3) → "Mar 2025"
 */
export function labelMes(ano, mes) {
  return `${MESES[mes - 1]} ${ano}`;
}
