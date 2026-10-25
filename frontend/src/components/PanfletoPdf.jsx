import { Document, Page, View, Text, Svg, Rect, Line, Path, Circle, Ellipse, Font, StyleSheet } from '@react-pdf/renderer';
import { formatarEuros } from '../utils/formatacao';
import dmSans400 from '../assets/fonts/dm-sans-v17-latin-regular.ttf';
import dmSans500 from '../assets/fonts/dm-sans-v17-latin-500.ttf';

// O panfleto em PDF: um retrato dos hábitos dos últimos 12 meses completos,
// numa só página. Desenha-se com o @react-pdf/renderer, e não com o Recharts,
// que só funciona no ecrã; por isso os gráficos são SVG simples, feitos à mão.
// As fontes vão em TTF: o @react-pdf/renderer falha a embutir as WOFF2 com
// letras acentuadas

Font.register({
    family: 'DM Sans',
    fonts: [{ src: dmSans400 }, { src: dmSans500, fontWeight: 500 }],
});
// Sem hifenização: o PDF partia as palavras portuguesas em sítios errados
Font.registerHyphenationCallback(palavra => [palavra]);

// As cores do tema claro da aplicação (index.css)
const COR = {
    fundo: '#eef1f4',
    ponto: '#d3d8df',
    cartao: '#ffffff',
    tinta: '#2b2f36',
    suave: '#5b6270',
    accent: '#3a86d1',
    accentMuted: '#6f8fb0',
    receita: '#257049',
    receitaFundo: '#d7f0e0',
    receitaFace: '#5aae7e',
    despesa: '#a8403e',
    despesaFundo: '#f9dcdc',
    despesaClara: '#e3a19f',
    investimento: '#776549',
    investimentoFundo: '#f5e6c8',
    investimentoLinha: '#d9b885',
    borda: '#c7cdd6',
    sombra: '#1e283c',
};

// A cor de cada cenário da projecção, pela taxa de rendimento anual, e os anos
// em que se lê o valor de cada um
const COR_CENARIO = { 0: COR.accent, 4: COR.accentMuted, 7: COR.investimentoLinha };
const MARCOS = [2, 5, 10];

// A cor de uma barra ou de uma legenda da despesa, pela classificação
const COR_CLASSE = { essencial: COR.despesa, evitavel: COR.despesaClara, null: COR.borda };

const LARGURA = 595;
const ALTURA = 842;
const MARGEM = 32;

// Os números do panfleto arredondam-se ao euro: lê-se melhor e o cêntimo não
// muda nenhuma conclusão. O espaço antes do € não quebra, para o € não ficar
// sozinho no início de uma linha
const euros = v => formatarEuros(v, 0).replace(' €', ' €');

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho',
    'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
const nomeMes = ({ ano, mes }) => `${MESES[mes - 1]} de ${ano}`;
const nomeDia = iso => {
    const [ano, mes, dia] = iso.split('-').map(Number);
    return `${dia} de ${MESES[mes - 1]} de ${ano}`;
};

const s = StyleSheet.create({
    pagina: { backgroundColor: COR.fundo, color: COR.tinta, fontFamily: 'DM Sans', fontSize: 9.5, lineHeight: 1.4 },
    titulo: { fontSize: 14, fontWeight: 500, marginBottom: 8 },
    suave: { color: COR.suave },
    numero: { fontWeight: 500, lineHeight: 1 },
});

// O fundo de papel ponteado, como o da aplicação
function Pontos() {
    const passo = 16;
    const pontos = [];
    for (let y = passo / 2; y < ALTURA; y += passo) {
        for (let x = passo / 2; x < LARGURA; x += passo) {
            pontos.push(<Circle key={`${x}-${y}`} cx={x} cy={y} r={0.8} fill={COR.ponto} />);
        }
    }
    return <Svg style={{ position: 'absolute', top: 0, left: 0 }} width={LARGURA} height={ALTURA - 1}>{pontos}</Svg>;
}

// Um cartão pousado na página, numa posição fixa, com uma sombra suave feita
// de camadas (o PDF não tem sombras desfocadas). Pode rodar um pouco e
// sobrepor-se aos vizinhos, mas só nas margens, sem tapar o conteúdo
function Cartao({ x, y, w, h, cor = COR.cartao, rodar = 0, raio = 18, padding = 18, children }) {
    return (
        <View style={{ position: 'absolute', left: x, top: y, width: w, height: h, transform: `rotate(${rodar}deg)` }}>
            {[1, 2, 3, 4, 5].map(i => (
                <View key={i} style={{
                    position: 'absolute', left: -i * 0.6, top: 2 + i * 1.6, width: w + i * 1.2, height: h + i * 0.6,
                    borderRadius: raio + i, backgroundColor: COR.sombra, opacity: 0.022,
                }} />
            ))}
            <View style={{ width: w, height: h, borderRadius: raio, backgroundColor: cor, padding }}>
                {children}
            </View>
        </View>
    );
}

// Uma moeda com volume: o rebordo, a face e um reflexo
function Moeda({ cx, cy, r, cor, rebordo }) {
    return (
        <>
            <Circle cx={cx} cy={cy + 1.2} r={r} fill={rebordo} />
            <Circle cx={cx} cy={cy} r={r} fill={cor} />
            <Circle cx={cx} cy={cy} r={r * 0.72} fill="none" stroke={rebordo} strokeWidth={0.6} strokeOpacity={0.5} />
            <Ellipse cx={cx - r * 0.3} cy={cy - r * 0.4} rx={r * 0.38} ry={r * 0.2} fill="#ffffff" fillOpacity={0.45} />
        </>
    );
}

// De cada 100 € que entram, quantos se gastam e quantos ficam: 100 moedas
function Moedas({ gastos }) {
    const r = 10;
    const passo = 25;
    return (
        <Svg width={passo * 10} height={passo * 10 + 2}>
            {Array.from({ length: 100 }, (_, i) => (
                <Moeda
                    key={i}
                    cx={(i % 10) * passo + passo / 2}
                    cy={Math.floor(i / 10) * passo + passo / 2}
                    r={r}
                    cor={i < gastos ? '#cf6a67' : COR.receitaFace}
                    rebordo={i < gastos ? COR.despesa : COR.receita}
                />
            ))}
        </Svg>
    );
}

// Um valor dentro de um campo, como os da aplicação: o panfleto sai dos dados,
// não é uma folha feita uma vez. Alguns campos têm o cursor de texto, da
// altura do número (`cursor`); o activo tem também a borda do destaque
function Campo({ children, cursor = 0, activo = false, style }) {
    return (
        <View style={[{
            flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start',
            backgroundColor: COR.cartao, borderWidth: activo ? 1.4 : 1, borderColor: activo ? COR.accent : COR.borda,
            borderRadius: 6, paddingVertical: 3, paddingHorizontal: 7,
        }, style]}>
            {children}
            {cursor > 0 && <View style={{ width: cursor > 20 ? 1.8 : 1.2, height: cursor, backgroundColor: COR.accent, marginLeft: 3 }} />}
        </View>
    );
}

// As subcategorias onde vai mais dinheiro, em barras
function Gastos({ despesas, mes }) {
    const maior = Math.max(...despesas.top.map(d => d.mensal));
    const larguraBarra = 96;
    return (
        <>
            <Text style={s.titulo}>Em que é que gasto</Text>
            {despesas.top.map((d, i) => (
                <View key={i} style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 5.5 }}>
                    <Text style={{ width: 76 }}>{d.subcategoria}</Text>
                    <Svg width={larguraBarra} height={9}>
                        <Rect x={0} y={0} width={(d.mensal / maior) * larguraBarra} height={9} rx={4.5}
                            fill={COR_CLASSE[d.classe]} />
                    </Svg>
                    <Text style={{ flex: 1, textAlign: 'right', fontWeight: 500 }}>{euros(d.mensal)}</Text>
                </View>
            ))}
            <View style={{ flexDirection: 'row', marginTop: 1 }}>
                <Text style={[s.suave, { flex: 1 }]}>Outras {despesas.outras.quantas}</Text>
                <Text style={s.suave}>{euros(despesas.outras.mensal)}</Text>
            </View>
            <View style={{ flexDirection: 'row', marginTop: 8 }}>
                {[['Essencial', mes.essencial, COR_CLASSE.essencial], ['Evitável', mes.evitavel, COR_CLASSE.evitavel],
                    ['Sem classificação', mes.sem_classe, COR_CLASSE.null]].filter(([, valor]) => valor > 0).map(([nome, valor, cor]) => (
                    <View key={nome} style={{ flexDirection: 'row', alignItems: 'center', marginRight: 14 }}>
                        <View style={{ width: 7, height: 7, borderRadius: 3.5, backgroundColor: cor, marginRight: 5 }} />
                        <Text style={s.suave}>{nome} {euros(valor)}</Text>
                    </View>
                ))}
            </View>
        </>
    );
}

// A projecção: as três curvas até 10 anos, com o valor de cada uma aos 2, 5 e
// 10 anos
function Projecao({ projecao, atual, poupanca }) {
    const largura = 230;
    const altura = 92;
    const topo = Math.max(...projecao.map(c => c.valores[c.valores.length - 1]));
    const meses = projecao[0].valores.length - 1;
    const px = m => 4 + (m / meses) * (largura - 8);
    const py = v => altura - (v / topo) * (altura - 6);
    const caminho = valores => valores.map((v, m) => `${m === 0 ? 'M' : 'L'}${px(m).toFixed(1)},${py(v).toFixed(1)}`).join(' ');

    return (
        <>
            <Text style={s.titulo}>Se mantiver estes hábitos</Text>
            <View style={{ flexDirection: 'row' }}>
                <Svg width={largura} height={altura + 14}>
                    {[2, 5, 10].map(anos => (
                        <Line key={anos} x1={px(anos * 12)} y1={0} x2={px(anos * 12)} y2={altura} stroke={COR.fundo} strokeWidth={1} />
                    ))}
                    {projecao.map(c => (
                        <Path key={c.taxa} d={caminho(c.valores)} stroke={COR_CENARIO[c.taxa]} strokeWidth={c.taxa === 0 ? 2.5 : 2} fill="none" strokeLinecap="round" />
                    ))}
                    <Circle cx={px(0)} cy={py(atual)} r={3.5} fill={COR.tinta} />
                    {[['Hoje', 0], ['2 anos', 24], ['5 anos', 60], ['10 anos', 120]].map(([nome, m]) => (
                        <Text key={nome} x={px(m)} y={altura + 11} style={{ fontSize: 7.5, fontFamily: 'DM Sans' }} fill={COR.suave}
                            textAnchor={m === 0 ? 'start' : m === 120 ? 'end' : 'middle'}>{nome}</Text>
                    ))}
                </Svg>

                <View style={{ flex: 1, marginLeft: 18 }}>
                    <View style={{ flexDirection: 'row', marginBottom: 3 }}>
                        <View style={{ width: 74 }} />
                        {MARCOS.map(anos => (
                            <Text key={anos} style={[s.suave, { flex: 1, textAlign: 'right', fontSize: 8 }]}>{anos} anos</Text>
                        ))}
                    </View>
                    {projecao.map(c => (
                        <View key={c.taxa} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 3 }}>
                            <View style={{ width: 74, flexDirection: 'row', alignItems: 'center' }}>
                                <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: COR_CENARIO[c.taxa], marginRight: 6 }} />
                                <Text>{c.taxa === 0 ? 'Só poupança' : `Com ${c.taxa} %`}</Text>
                            </View>
                            {MARCOS.map(anos => (
                                <Text key={anos} style={{ flex: 1, textAlign: 'right', fontWeight: c.taxa === 0 ? 500 : 400 }}>
                                    {euros(c.valores[anos * 12])}
                                </Text>
                            ))}
                        </View>
                    ))}
                    <Text style={[s.suave, { fontSize: 7.5, marginTop: 6 }]}>
                        Somo {euros(poupanca)} por mês do que poupo. Com 4 % ou 7 %, os investimentos rendem essa
                        taxa por ano. O rendimento não é garantido: é o efeito dos juros compostos, não uma previsão.
                    </Text>
                </View>
            </View>
        </>
    );
}

export default function PanfletoPdf({ dados }) {
    const { periodo, mes, despesas, patrimonio, projecao } = dados;
    // De cada 100 € recebidos, quantos se gastam. Sem receita não há conta; com
    // mais despesa do que receita, os números mostram-no, e as moedas ficam
    // todas na cor da despesa
    const gastos = mes.receita > 0 ? Math.round((mes.despesa / mes.receita) * 100) : null;
    const porCem = valor => (gastos === null ? '—' : `${valor} €`);

    return (
        <Document title="O meu retrato financeiro" language="pt-PT">
            <Page size="A4" style={s.pagina}>
                <Pontos />

                {/* As moedas, o cartão maior; os dois números pousam na sua margem direita */}
                <Cartao x={MARGEM} y={92} w={330} h={318} padding={22}>
                    <Text style={{ fontSize: 13, marginBottom: 12 }}>De cada 100 € que recebo,</Text>
                    <Moedas gastos={Math.min(100, Math.max(0, gastos ?? 0))} />
                </Cartao>

                {/* O título, pousado por cima do cartão das moedas, com o período em campos */}
                <Cartao x={MARGEM - 6} y={22} w={372} h={80} rodar={-1} padding={14}>
                    <Text style={{ fontSize: 28, fontWeight: 500, letterSpacing: -0.6, lineHeight: 1 }}>O meu retrato financeiro</Text>
                    <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 9 }}>
                        <Text style={[s.suave, { marginRight: 6 }]}>De</Text>
                        <Campo><Text>{nomeMes(periodo.de)}</Text></Campo>
                        <Text style={[s.suave, { marginHorizontal: 6 }]}>a</Text>
                        <Campo activo cursor={12}><Text>{nomeMes(periodo.ate)}</Text></Campo>
                    </View>
                </Cartao>

                <Cartao x={318} y={118} w={245} h={112} cor={COR.despesaFundo} rodar={-2}>
                    <Text style={[s.numero, { fontSize: 56, color: COR.despesa }]}>{porCem(gastos)}</Text>
                    <Text style={{ fontSize: 12, color: COR.despesa, marginTop: 6 }}>vão para despesas</Text>
                </Cartao>

                <Cartao x={330} y={222} w={233} h={112} cor={COR.receita} rodar={1.5}>
                    <Text style={[s.numero, { fontSize: 56, color: '#ffffff' }]}>{porCem(100 - gastos)}</Text>
                    <Text style={{ fontSize: 12, color: '#ffffff', marginTop: 6 }}>ficam comigo</Text>
                </Cartao>

                {/* O mês normal, a fechar o cartão das moedas por baixo */}
                <Cartao x={316} y={350} w={247} h={68} padding={16}>
                    <View style={{ flexDirection: 'row' }}>
                        {[['Recebo', mes.receita, COR.receita], ['Gasto', mes.despesa, COR.despesa], ['Fica', mes.receita - mes.despesa, COR.receita, 13]].map(([nome, valor, cor, cursor]) => (
                            <View key={nome} style={{ flex: 1 }}>
                                <Text style={[s.suave, { fontSize: 8.5 }]}>{nome}, por mês</Text>
                                <Campo cursor={cursor} style={{ marginTop: 4 }}>
                                    <Text style={[s.numero, { fontSize: 13, color: cor }]}>{euros(valor)}</Text>
                                </Campo>
                            </View>
                        ))}
                    </View>
                </Cartao>

                <Cartao x={MARGEM} y={440} w={262} h={222}>
                    <Gastos despesas={despesas} mes={mes} />
                </Cartao>

                <Cartao x={282} y={462} w={281} h={186} cor={COR.receitaFundo}>
                    <Text style={s.titulo}>O que tenho</Text>
                    <Campo cursor={28} style={{ paddingVertical: 5, paddingHorizontal: 9, borderRadius: 8 }}>
                        <Text style={[s.numero, { fontSize: 30, color: COR.receita }]}>{euros(patrimonio.atual)}</Text>
                    </Campo>
                    <Text style={[s.suave, { marginTop: 7, maxWidth: 160 }]}>
                        {euros(patrimonio.liquidez)} em contas, {euros(patrimonio.investimentos)} investidos
                        e {euros(patrimonio.bens)} em bens
                    </Text>
                    {/* Com menos de 3 meses não há crescimento */}
                    {patrimonio.crescimento !== null && (
                        <>
                            <Text style={[s.suave, { marginTop: 12 }]}>Cresce por mês</Text>
                            <Text style={[s.numero, { fontSize: 19, marginTop: 4 }]}>
                                {patrimonio.crescimento > 0 ? '+' : ''}{euros(patrimonio.crescimento)}
                            </Text>
                            <Text style={[s.suave, { fontSize: 8, marginTop: 4 }]}>
                                {euros(patrimonio.poupanca)} do que poupo e {euros(patrimonio.valorizacao)} da valorização
                            </Text>
                        </>
                    )}
                </Cartao>

                {/* O investimento do período, pousado no canto do património */}
                <Cartao x={441} y={430} w={136} h={68} cor={COR.investimentoFundo} rodar={3} padding={12}>
                    <Text style={{ fontSize: 8.5, color: COR.investimento }}>Investi em {periodo.meses} meses</Text>
                    <Campo cursor={17} style={{ marginTop: 5 }}>
                        <Text style={[s.numero, { fontSize: 18, color: COR.investimento }]}>{euros(patrimonio.investido)}</Text>
                    </Campo>
                </Cartao>

                <Cartao x={MARGEM} y={668} w={LARGURA - MARGEM * 2} h={140} padding={16}>
                    {projecao ? (
                        <Projecao projecao={projecao} atual={patrimonio.atual} poupanca={patrimonio.poupanca} />
                    ) : (
                        <>
                            <Text style={s.titulo}>Se mantiver estes hábitos</Text>
                            <Text style={s.suave}>A projeção precisa de pelo menos 3 meses de histórico.</Text>
                        </>
                    )}
                </Cartao>

                <Text style={[s.suave, { position: 'absolute', left: MARGEM, right: MARGEM, bottom: 14, fontSize: 7.5 }]}>
                    Gerado a {nomeDia(dados.gerado_em)} a partir dos meus dados. Médias de {periodo.meses} meses completos,
                    sem as compras extraordinárias ({euros(mes.extraordinarias)} no período).
                </Text>
            </Page>
        </Document>
    );
}
