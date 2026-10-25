// O filtro de ano em botões lado a lado. O valor é 'todos' ou o ano em texto,
// como o <select> que substitui
export default function SeletorAno({ anos, valor, onChange }) {
    const opcoes = ['todos', ...anos.map(String)];
    return (
        <div className="segmentado" role="group" aria-label="Filtro de ano">
            {opcoes.map(o => (
                <button
                    key={o}
                    className={o === valor ? 'activo' : ''}
                    aria-pressed={o === valor}
                    onClick={() => onChange(o)}
                >
                    {o === 'todos' ? 'Todos' : o}
                </button>
            ))}
        </div>
    );
}
