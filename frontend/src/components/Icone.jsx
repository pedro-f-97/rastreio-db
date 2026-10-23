// Ícones de traço, desenhados à mão no estilo do resto da app. Herdam a cor do
// texto (currentColor) e o tamanho vem por propriedade
const TRACOS = {
    editar: ['M12 20h9', 'M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z'],
    apagar: ['M3 6h18', 'M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6', 'M10 11v6', 'M14 11v6', 'M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2'],
    fechar: ['M18 6 6 18', 'M6 6l12 12'],
    mais: ['M12 5v14', 'M5 12h14'],
    confirmar: ['M20 6 9 17l-5-5'],
    baixo: ['m6 9 6 6 6-6'],
    direita: ['m9 18 6-6-6-6'],
    esquerda: ['m15 18-6-6 6-6'],
    procurar: ['M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z', 'm21 21-4.3-4.3'],
    descarregar: ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'M7 10l5 5 5-5', 'M12 15V3'],
    carregar: ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'M17 8l-5-5-5 5', 'M12 3v12'],
    info: ['M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z', 'M12 16v-4', 'M12 8h.01'],
    aviso: ['M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z', 'M12 9v4', 'M12 17h.01'],
    desfazer: ['M9 14 4 9l5-5', 'M4 9h10.5a5.5 5.5 0 0 1 0 11H11'],
    ficheiro: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z', 'M14 2v6h6'],
    menu: ['M12 5h.01', 'M12 12h.01', 'M12 19h.01'],
    sol: ['M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z', 'M12 2v2', 'M12 20v2', 'm4.9 4.9 1.4 1.4', 'm17.7 17.7 1.4 1.4', 'M2 12h2', 'M20 12h2', 'm6.3 17.7-1.4 1.4', 'm19.1 4.9-1.4 1.4'],
    lua: ['M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z'],
    // Navegação
    transacoes: ['M8 6h13', 'M8 12h13', 'M8 18h13', 'M3 6h.01', 'M3 12h.01', 'M3 18h.01'],
    historico: ['M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z', 'M16 2v4', 'M8 2v4', 'M3 10h18'],
    importacao: ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'M7 10l5 5 5-5', 'M12 15V3'],
    categorias: ['M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6a2 2 0 0 1 0 2.8Z', 'M7 7h.01'],
    regras: ['M22 3H2l8 9.5V19l4 2v-8.5Z'],
    contas: ['M21 12V7H5a2 2 0 0 1 0-4h14v4', 'M3 5v14a2 2 0 0 0 2 2h16v-5', 'M18 12a2 2 0 0 0 0 4h4v-4Z'],
    tipos: ['m12 2 10 5-10 5L2 7Z', 'm2 17 10 5 10-5', 'm2 12 10 5 10-5'],
    estatisticas: ['M3 3v18h18', 'M7 16v-5', 'M12 16V8', 'M17 16V7'],
    ativos: ['M21.2 15.9A10 10 0 1 1 8 2.8', 'M22 12A10 10 0 0 0 12 2v10Z'],
    patrimonio: ['m22 7-8.5 8.5-5-5L2 17', 'M16 7h6v6'],
    conceitos: ['M4 19.5A2.5 2.5 0 0 1 6.5 17H20', 'M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z'],
};

export default function Icone({ nome, tamanho = 16, largura = 1.7, className = '' }) {
    return (
        <svg
            className={`icone ${className}`}
            width={tamanho}
            height={tamanho}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={nome === 'menu' ? 3 : largura}
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
        >
            {TRACOS[nome].map(d => <path key={d} d={d} />)}
        </svg>
    );
}
