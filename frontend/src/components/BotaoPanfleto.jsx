import { useState } from 'react';
import { obterPanfleto } from '../api/estatisticas';
import Icone from './Icone';

// O botão da barra lateral que gera o panfleto em PDF e o descarrega. A
// biblioteca do PDF só se carrega aqui, ao carregar no botão: é grande, e o
// resto da aplicação não precisa dela
export default function BotaoPanfleto() {
    const [aGerar, setAGerar] = useState(false);

    async function gerar() {
        setAGerar(true);
        try {
            const [{ data }, { pdf }, { default: PanfletoPdf }] = await Promise.all([
                obterPanfleto(),
                import('@react-pdf/renderer'),
                import('./PanfletoPdf'),
            ]);
            const ficheiro = await pdf(<PanfletoPdf dados={data} />).toBlob();
            const url = URL.createObjectURL(ficheiro);
            const ligacao = document.createElement('a');
            ligacao.href = url;
            const { ano, mes } = data.periodo.ate;
            ligacao.download = `retrato-financeiro-${ano}-${String(mes).padStart(2, '0')}.pdf`;
            ligacao.click();
            // Revogar logo a seguir ao clique podia cortar o download
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (e) {
            alert(e.response?.data?.detail || 'Não foi possível gerar o PDF.');
        } finally {
            setAGerar(false);
        }
    }

    return (
        <button className="sidebar-link" onClick={gerar} disabled={aGerar}>
            <Icone nome="ficheiro" tamanho={17} />
            <span className="sidebar-link-conteudo">{aGerar ? 'A gerar…' : 'Retrato em PDF'}</span>
        </button>
    );
}
