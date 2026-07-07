import { useEffect, useRef, useState } from 'react'
import { useGuia } from '../contexts/GuiaContext'
import './GuiaDestaque.css'

export default function GuiaDestaque() {
  const { activo, passo, passoActual, totalPassos, avancar, sair } = useGuia()
  const [posicao, setPosicao] = useState(null)
  const elementoActualRef = useRef(null)

  useEffect(() => {
    if (!activo) return

    const elementoAnterior = elementoActualRef.current
    if (elementoAnterior) {
      elementoAnterior.classList.remove('guia-glow')
      elementoActualRef.current = null
    }

    if (!passo.dataTour) {
      setPosicao(null)
      return
    }

    let tentativas = 0
    let cancelado = false

    function actualizarPosicao(elemento) {
      const rect = elemento.getBoundingClientRect()
      const metadeEcra = window.innerHeight / 2
      const noTopo = rect.top < metadeEcra

      setPosicao(
        noTopo
          ? { left: rect.left, top: rect.bottom + 12, modo: 'baixo' }
          : { left: rect.left, bottom: window.innerHeight - rect.top + 12, modo: 'cima' }
      )
    }

    function tentarLocalizar() {
      if (cancelado) return
      const elemento = document.querySelector(`[data-tour="${passo.dataTour}"]`)
      if (elemento) {
        elemento.classList.add('guia-glow')
        elementoActualRef.current = elemento
        actualizarPosicao(elemento)
      } else if (tentativas < 10) {
        tentativas += 1
        setTimeout(tentarLocalizar, 100)
      }
    }

    tentarLocalizar()

    function aoRedimensionarOuScroll() {
      if (elementoActualRef.current) {
        actualizarPosicao(elementoActualRef.current)
      }
    }
    window.addEventListener('resize', aoRedimensionarOuScroll)
    window.addEventListener('scroll', aoRedimensionarOuScroll, true)

    return () => {
      cancelado = true
      window.removeEventListener('resize', aoRedimensionarOuScroll)
      window.removeEventListener('scroll', aoRedimensionarOuScroll, true)
      if (elementoActualRef.current) {
        elementoActualRef.current.classList.remove('guia-glow')
      }
    }
  }, [activo, passo])

  if (!activo) return null

  const centrado = !passo.dataTour

  const estiloCaixa = centrado
    ? undefined
    : {
        left: posicao?.left ?? -9999,
        ...(posicao?.modo === 'cima'
          ? { bottom: posicao.bottom }
          : { top: posicao?.top ?? -9999 }),
      }

  return (
    <div
      className={`guia-caixa ${centrado ? 'guia-caixa-centrada' : ''}`}
      style={estiloCaixa}
    >
      <p className="guia-texto">{passo.texto}</p>
      <div className="guia-rodape">
        <span className="guia-progresso">{passoActual + 1} / {totalPassos}</span>
        <div className="guia-botoes">
          <button className="guia-botao-sair" onClick={sair}>Sair</button>
          <button className="guia-botao-ok" onClick={avancar}>OK</button>
        </div>
      </div>
    </div>
  )
}