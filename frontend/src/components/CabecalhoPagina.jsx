// O cabeçalho comum das páginas: a secção da navegação por cima, o título, uma
// frase opcional a explicar a página e as acções à direita
export default function CabecalhoPagina({ secao, titulo, descricao, children }) {
    return (
        <header className="cabecalho-pagina">
            <div className="cabecalho-texto">
                {secao && <span className="cabecalho-secao">{secao}</span>}
                <h1 className="titulo-pagina">{titulo}</h1>
                {descricao && <p className="cabecalho-descricao">{descricao}</p>}
            </div>
            {children && <div className="cabecalho-accoes">{children}</div>}
        </header>
    );
}
