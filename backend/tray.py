import sys
import os

def iniciar_tray(parar_servidor_fn):
    import tkinter as tk

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

    # Centra a janela no ecrã
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - 110
    y = (root.winfo_screenheight() // 2) - 50
    root.geometry(f"220x100+{x}+{y}")

    tk.Label(root, text="rastreio-db", font=("Helvetica", 13, "bold")).pack(pady=(14, 8))
    tk.Button(root, text="Abrir no browser", command=ao_abrir, width=20).pack(pady=2)
    tk.Button(root, text="Sair", command=ao_sair, width=20).pack(pady=2)

    root.mainloop()