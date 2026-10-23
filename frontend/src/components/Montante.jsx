import { classeValor, formatarEuros, prefixoSinal } from '../utils/formatacao';

// Um valor em euros para os números grandes: os cêntimos e o € mais pequenos
// que a parte inteira. `cor` pinta-o pelo sinal e `sinal` põe o «+» nos
// positivos, como nos resultados
export default function Montante({ valor, casas = 2, cor = false, sinal = false, sufixo = null, className = '' }) {
    const classes = `montante ${cor && valor != null ? classeValor(valor, casas) : ''} ${className}`;
    if (valor == null) return <span className={classes}>—</span>;
    // "1 234,56 €": sem o " €", e a vírgula separa os cêntimos
    const numero = formatarEuros(valor, casas).slice(0, -2);
    const virgula = numero.lastIndexOf(',');
    const inteiro = virgula === -1 ? numero : numero.slice(0, virgula);
    const decimal = virgula === -1 ? '' : numero.slice(virgula);
    return (
        <span className={classes}>
            {sinal && prefixoSinal(valor, casas)}
            {inteiro}
            <span className="montante-menor">{decimal}</span>
            <span className="montante-moeda">€{sufixo}</span>
        </span>
    );
}
