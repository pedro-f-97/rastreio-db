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