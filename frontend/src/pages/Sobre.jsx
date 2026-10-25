import { useGuia } from '../contexts/GuiaContext';
import './Sobre.css';
import '../componentes.css';
import CabecalhoPagina from '../components/CabecalhoPagina';

export default function Sobre() {
    const { reiniciar } = useGuia();

    return (
        <div className="pagina-container sobre-page">
            <CabecalhoPagina
                secao="Ajuda"
                titulo="Conceitos"
                descricao="Como a aplicação pensa: contas, categorias, regras e património."
            >
                <button className="btn-secundario" onClick={reiniciar}>
                    Reiniciar tour guiado
                </button>
            </CabecalhoPagina>

            <section className="sobre-seccao" data-numero="01">
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

            <section className="sobre-seccao" data-numero="02">
                <h2>Verificação do saldo e transações manuais</h2>
                <p>
                    O saldo de cada conta é calculado a partir do saldo de referência e das transações. Para
                    confirmar que não falta nenhuma, compara-se com o saldo que o banco indica: o do extracto,
                    quando o traz, ou, nas contas cujo extracto não o traz, um saldo que escreves de vez em quando
                    numa transação (por exemplo, uma vez por mês). Escreve sempre o saldo da conta no fim desse
                    dia. O saldo de referência também conta como um saldo certo.
                </p>
                <p>
                    A verificação corre sozinha ao abrir a página Transações, para todas as contas activas, e
                    também quando importas um extracto, quando crias ou apagas uma transação manual e quando
                    escreves um saldo. Se houver diferenças, mostra entre que datas a diferença mudou: é aí que
                    está a transação em falta ou a mais. Se o último saldo tiver mais de 31 dias,
                    contados da última transação, sugere que escrevas um novo.
                </p>
                <p>
                    Para corrigir uma diferença, podes criar uma transação à mão, mas não é recomendado: o normal
                    é importar o extracto. As transações manuais ficam marcadas e são as únicas que se podem
                    apagar; as importadas só saem ao desfazer a importação.
                </p>
                <div className="sobre-relacao">
                    <span>Transação</span>
                    <span className="sobre-seta">→</span>
                    <span>saldo</span>
                    <span className="sobre-seta">·</span>
                    <span>manual</span>
                </div>
            </section>

            <section className="sobre-seccao" data-numero="03">
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

            <section className="sobre-seccao" data-numero="04">
                <h2>Classificação das despesas</h2>
                <p>
                    Cada subcategoria de uma categoria de despesa pode ter uma classificação:{' '}
                    <strong>Essencial</strong>, o que se precisa e se repete (supermercado, renda, combustível, seguro);{' '}
                    <strong>Evitável</strong>, o que é dispensável e se repete (restauração, jogos, viagens); ou{' '}
                    <strong>Extraordinária</strong>, uma compra isolada que não se espera repetir nos próximos dois ou
                    três anos (um carro, um computador). Sem classificação, a subcategoria conta como as outras.
                </p>
                <p>
                    As médias e as taxas das Estatísticas contam só os meses completos: o mês em curso fica de
                    fora até acabar, mas entra nos totais e nos gráficos mês a mês.
                </p>
                <p>
                    Nas Estatísticas, o <strong>mês típico</strong> é a média mensal da despesa sem as extraordinárias,
                    que aparecem sempre à parte, com o total do período. As despesas anuais, como o seguro ou o IUC,
                    não são extraordinárias: contam na média, repartidas pelos meses. A classificação é da subcategoria
                    e vale para todas as suas transações; para separar uma compra grande, cria-se outra subcategoria.
                    Se a categoria deixar de ser de despesa, as suas subcategorias perdem a classificação.
                </p>
                <div className="sobre-relacao">
                    <span>Subcategoria</span>
                    <span className="sobre-seta">→</span>
                    <span>classe_despesa</span>
                </div>
            </section>

            <section className="sobre-seccao" data-numero="05">
                <h2>Regras</h2>
                <p>
                    Uma regra associa um padrão de descrição a uma categoria e subcategoria, e é aplicada
                    automaticamente às transações importadas que correspondam a esse padrão. Ao criar uma regra, ela
                    é logo aplicada às transações já existentes que estejam por categorizar, ou que tenham a mesma
                    categoria e ainda não tenham subcategoria; as que já têm outra categoria não são tocadas. Para
                    essas, o botão «Aplicar regras às transações», na página Regras, mostra os conflitos com a
                    categorização anterior e deixa decidir transação a transação. Uma regra não se edita: para a
                    mudar, apaga-se e cria-se de novo.
                </p>
                <p>
                    Uma regra também pode ser marcada para <strong>nunca atribuir categoria</strong> — útil para
                    padrões de descrição onde o contexto varia demasiado de transação para transação (por exemplo,
                    transferências entre contas próprias). Nesse caso, a regra serve apenas para identificar a
                    transação, deixando a categorização manual.
                </p>
            </section>

            <section className="sobre-seccao" data-numero="06">
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
                <p>
                    O <strong>crescimento por mês</strong> é a tendência do património no fim de cada mês, e não a
                    diferença entre o primeiro e o último: um mês fora do normal pesa pouco. Divide-se no que vem
                    da <strong>valorização</strong> dos ativos (o que valem acima do custo, mais o ganho já realizado)
                    e no que vem do <strong>que poupas</strong>. Comprar um ativo não muda nenhuma das duas. Conta só
                    os meses completos do filtro de ano, sem o mês em curso, e precisa de pelo menos 3.
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

            <section className="sobre-seccao" data-numero="07">
                <h2>Versão</h2>
                <p>{import.meta.env.VITE_VERSAO}</p>
            </section>
        </div>
    );
}