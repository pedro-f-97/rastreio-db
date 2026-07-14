import sys
import os

def iniciar_tray(parar_servidor_fn):
    import tkinter as tk

    # Mesmo critério de deteção de contexto usado no database.py
    if getattr(sys, 'frozen', False):
        BASE_DIR = os.path.dirname(sys.executable)
    else:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    ICON_ICO = os.path.join(BASE_DIR, "assets", "icon.ico")
    ICON_PNG = os.path.join(BASE_DIR, "assets", "icon.png")

    def ao_abrir():
        import webbrowser
        webbrowser.open("http://localhost:9742")

    def ao_sair():
        parar_servidor_fn()
        root.destroy()

    root = tk.Tk()
    root.title("rastreio-db")
    root.resizable(False, False)
    root.geometry("220x100")

    # Ícone da janela — .ico no Windows, .png como alternativa multiplataforma
    try:
        if sys.platform.startswith("win") and os.path.exists(ICON_ICO):
            root.iconbitmap(ICON_ICO)
        elif os.path.exists(ICON_PNG):
            icone = tk.PhotoImage(file=ICON_PNG)
            root.iconphoto(True, icone)
    except tk.TclError:
        pass  # Falha a carregar o ícone não deve impedir a janela de abrir

    # Centra a janela no ecrã
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - 110
    y = (root.winfo_screenheight() // 2) - 50
    root.geometry(f"220x100+{x}+{y}")

    # Frame com padding em todas as margens
    frame = tk.Frame(root, padx=16, pady=12)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="rastreio-db", font=("Helvetica", 13, "bold")).pack(pady=(0, 8))
    tk.Button(frame, text="Abrir no browser", command=ao_abrir, width=20).pack(pady=2)
    tk.Button(frame, text="Sair", command=ao_sair, width=20).pack(pady=2)

    root.mainloop()