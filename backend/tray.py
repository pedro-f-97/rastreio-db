import json
import os
import socket
import subprocess
import sys
import urllib.request


def quem_esta_na_porta(porta: int) -> str:
    """O que está à escuta em `127.0.0.1:<porta>`, antes de a aplicação arrancar.

    Devolve "livre" se ninguém aceita a ligação, "rastreio" se responde como o
    Rastreio-DB (outra instância aberta) e "outro" se é outro programa.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        if s.connect_ex(("127.0.0.1", porta)) != 0:
            return "livre"
    try:
        url = f"http://127.0.0.1:{porta}/api/configuracao/estado"
        with urllib.request.urlopen(url, timeout=2) as resposta:
            dados = json.load(resposta)
    except Exception:
        return "outro"
    if isinstance(dados, dict) and set(dados) == {"inicializado", "tour_visto"}:
        return "rastreio"
    return "outro"


def mostrar_erro(mensagem: str) -> None:
    """Mostra um erro do arranque numa caixa de diálogo (achado 7.4).

    No executável não há consola, e sem isto o erro só ia para o log. Se o
    tkinter não existir ou não houver ecrã, não faz nada: o erro continua no log.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox

        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror("Rastreio-DB", mensagem, parent=raiz)
        raiz.destroy()
    except Exception:
        pass


def iniciar_tray(parar_servidor_fn, porta):
    import tkinter as tk

    if getattr(sys, "frozen", False):
        BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    ICON_ICO = os.path.join(BASE_DIR, "assets", "icon.ico")
    ICON_SIZES = [16, 32, 48, 128, 256]
    ICON_PNGS = [os.path.join(BASE_DIR, "assets", f"icon-{s}.png") for s in ICON_SIZES]

    def ao_abrir():
        url = f"http://localhost:{porta}"

        if sys.platform.startswith("linux"):
            env = os.environ.copy()

            # Restaurar o ambiente original para o xdg-open,
            # evitando conflitos de bibliotecas do PyInstaller.
            if "LD_LIBRARY_PATH_ORIG" in env:
                env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
            else:
                env.pop("LD_LIBRARY_PATH", None)

            subprocess.Popen(
                ["xdg-open", url],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            import webbrowser

            webbrowser.open(url)

    def ao_sair():
        parar_servidor_fn()
        root.destroy()

    root = tk.Tk()
    root.title("rastreio-db")
    root.resizable(False, False)

    LARGURA, ALTURA = 260, 160

    try:
        if sys.platform.startswith("win") and os.path.exists(ICON_ICO):
            root.iconbitmap(ICON_ICO)
        else:
            icones = [tk.PhotoImage(file=p) for p in ICON_PNGS if os.path.exists(p)]
            # print(f"Ícones carregados: {len(icones)}")
            if icones:
                root.iconphoto(True, *icones)
    except tk.TclError:
        pass

    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (LARGURA // 2)
    y = (root.winfo_screenheight() // 2) - (ALTURA // 2)
    root.geometry(f"{LARGURA}x{ALTURA}+{x}+{y}")

    frame = tk.Frame(root, padx=16, pady=12)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="rastreio-db",
        font=("Helvetica", 13, "bold"),
    ).pack(pady=(0, 8))

    tk.Button(
        frame,
        text="Abrir no browser",
        command=ao_abrir,
        width=20,
    ).pack(pady=2)

    tk.Button(
        frame,
        text="Sair",
        command=ao_sair,
        width=20,
    ).pack(pady=2)

    root.mainloop()
