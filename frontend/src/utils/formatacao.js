/**
 * Formata um número como valor monetário em euros, por omissão ao cêntimo.
 * O formato toLocaleString('pt-PT') não separava corretamente os milhares.
 * Ex: 5233.75 → "5 233,75 €"; (5.877987, 4) → "5,8780 €"
 */
export function formatarEuros(valor, casas = 2) {
  if (valor == null) return "—";
  const formatador = new Intl.NumberFormat('pt-PT', {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
    useGrouping: true,
  });
  return formatador.format(valor) + " €";
}

const formatadorQuantidade = new Intl.NumberFormat('pt-PT', {
  maximumFractionDigits: 8,
  useGrouping: true,
});

/**
 * Formata uma quantidade (unidades de um ativo) com as casas decimais que
 * tiver, até 8, sem o ruído das somas em vírgula flutuante.
 * Ex: 0.1 + 0.2 = 0.30000000000000004 → "0,3"
 */
export function formatarQuantidade(valor) {
  if (valor == null) return "—";
  return formatadorQuantidade.format(valor);
}

/**
 * Formata uma percentagem com vírgula, por omissão com uma casa decimal.
 * Ex: 44.85 → "44,9%"; (2.345, 2) → "2,35%"
 */
export function formatarPercentagem(valor, casas = 1) {
  if (valor == null) return "—";
  const formatador = new Intl.NumberFormat('pt-PT', {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
    useGrouping: true,
  });
  return formatador.format(valor) + "%";
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
