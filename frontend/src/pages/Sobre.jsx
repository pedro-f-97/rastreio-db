import { useGuia } from '../contexts/GuiaContext';
import './Sobre.css';
import './Categorias.css';

export default function Sobre() {
    const { reiniciar } = useGuia();

    return (
        <div className="sobre-page">
            <div className="sobre-cabecalho">
                <h1>Conceitos</h1>
                <button className="sobre-botao-tour" onClick={reiniciar}>
                    Reiniciar tour guiado
                </button>
            </div>

            <section className="sobre-seccao">
                <h2>Contas, Perfis de Importação e Transações</h2>
                <p>
                    Cada perfil de importação é criado com base no formato do extracto de um banco específico e fica
                    associado a uma conta. Os perfis ficam guardados e podem ser reutilizados sempre que importares
                    um novo extracto do mesmo banco.
                </p>
                <p>
                    Cada transação importada fica sempre ligada a uma conta concreta — é essa ligação que permite
                    calcular saldos e agregações por conta em todo o resto da aplicação.
                </p>
                <div className="sobre-relacao">
                    <span>Conta</span>
                    <span className="sobre-seta">→</span>
                    <span>Perfil de Importação</span>
                    <span className="sobre-seta">→</span>
                    <span>Transação</span>
                </div>
            </section>

            <section className="sobre-seccao">
                <h2>Categorias</h2>
                <p>
                    Cada categoria tem um de quatro tipos:{' '}
                    <span className="badge-tipo badge-tipo-despesa">despesa</span>,{' '}
                    <span className="badge-tipo badge-tipo-receita">receita</span>,{' '}
                    <span className="badge-tipo badge-tipo-investimento">investimento</span> ou{' '}
                    <span className="badge-tipo badge-tipo-transferencia">transferência</span>. O tipo determina
                    como a categoria entra nas Estatísticas.
                </p>
                <p>
                    A poupança mensal é calculada como receitas mais despesas — as despesas entram sempre com sinal
                    negativo. O investimento é apresentado como uma linha informativa à parte e não é subtraído da poupança.
                </p>
                <div className="sobre-relacao">
                    <span>Receitas</span>
                    <span className="sobre-seta">+</span>
                    <span>Despesas (sinal negativo)</span>
                    <span className="sobre-seta">=</span>
                    <span>Poupança</span>
                </div>
            </section>

            <section className="sobre-seccao">
                <h2>Regras</h2>
                <p>
                    Uma regra associa um padrão de descrição a uma categoria e subcategoria, e é aplicada
                    automaticamente às transações importadas que correspondam a esse padrão. Ao criar ou editar uma
                    regra, podes optar por aplicá-la retroactivamente às transações já existentes; se houver
                    conflito com uma categorização manual anterior, a resolução é feita transação a transação.
                </p>
                <p>
                    Uma regra também pode ser marcada para <strong>nunca atribuir categoria</strong> — útil para
                    padrões de descrição onde o contexto varia demasiado de transação para transação (por exemplo,
                    transferências entre contas próprias). Nesse caso, a regra serve apenas para identificar a
                    transação, deixando a categorização manual.
                </p>
            </section>

            <section className="sobre-seccao">
                <h2>Património</h2>
                <p>
                    O património é composto por três tipos de activo: <strong>Liquidez</strong>,{' '}
                    <strong>Investimentos</strong> e <strong>Activos físicos</strong>.
                </p>
                <p>
                    Há dois campos que influenciam o tratamento dos activos: <code>Contabilização</code> é
                    definido ao criar o activo e diz respeito ao próprio activo, se deve ser tratado como investimento
                    , com resultados, ou apenas um activo do qual não é esperado retorno; <code>Património</code> é
                    definido na subcategoria e determina se as transações dessa subcategoria contam para o
                    património.
                </p>
                <div className="sobre-relacao">
                    <span>Subcategoria</span>
                    <span className="sobre-seta">→</span>
                    <span>trata_patrimonio</span>
                </div>
                <div className="sobre-relacao">
                    <span>Activo</span>
                    <span className="sobre-seta">→</span>
                    <span>contabilizacao</span>
                </div>
            </section>
        </div>
    );
}