"""
templates/agent_template.py
==============================
Copiá este archivo, renombralo, y completá las partes marcadas con TODO.

Un agente:
1. Se registra una sola vez en el orquestador: orchestrator.register_agent(MiAgente())
2. Coordina uno o más expertos (ver expert_template.py)
3. Termina process() de UNA de estas tres formas — elegí según lo que
   necesites, están explicadas abajo, en el punto donde corresponde.

No necesitás tocar nada del framework para agregar o sacar un agente.
Sacarlo es simplemente no llamar a register_agent() con él.
"""
from __future__ import annotations
from typing import Any

from sett import SETTAgent

# TODO: importá tu(s) experto(s) real(es). Este import de ejemplo asume
# que copiaste expert_template.py con el nombre my_expert.py al lado.
# from .my_expert import MyExpert


# TODO: renombrá la clase y el dominio con el nombre de tu especialidad
# (ej: HealthAgent/"health", WeatherAgent/"weather")
class MyAgent(SETTAgent):
    """
    TODO: una línea describiendo de qué dominio se especializa este agente.
    Ejemplo: "Monitorea signos vitales y evalúa riesgo de salud."
    """

    def __init__(self) -> None:
        super().__init__(name="MyAgent", domain="my_domain")

        # TODO: registrá acá cada experto que este agente coordina.
        # Podés tener uno solo, o varios — no hay un número fijo
        # correcto, depende de cuántas tareas distintas necesita tu
        # dominio. Ver CONVENTIONS.md cuando exista.
        # self.register_expert(MyExpert(name="mi_experto"))
        pass

    def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        # TODO: llamá a tu(s) experto(s) y combiná sus resultados.
        # resultado = self.get_expert("mi_experto").resolve(input_data)
        resultado: dict[str, Any] = {}

        # ── Elegí UNA de estas tres formas de cerrar process() ─────────
        #
        # (A) Este agente solo informa un estado — no ejecuta ningún
        #     efecto en el mundo real (no manda nada, no llama a nadie).
        #     Es el caso más común. El resultado pasa por el
        #     EthicalFilter antes de guardarse en memoria universal.
        #
        # self._publish_to_universal(resultado)
        # return resultado

        # (B) Este agente SÍ produce un efecto real (mandar un mensaje,
        #     llamar una API), pero no configuraste un SETTExecutor
        #     todavía, o es algo de bajo riesgo/prototipo rápido. Se
        #     evalúa contra el EthicalFilter ANTES de que vos mismo
        #     ejecutes el efecto a continuación de esta llamada.
        #
        # self.propose_action("mi_accion", action_context=input_data)
        # (acá recién, si no se bloqueó, ejecutás vos el efecto real)
        # return resultado

        # (C) Este agente produce un efecto real y querés la garantía
        #     estructural completa: este agente NUNCA toca el cliente
        #     real (SMS, API, lo que sea) — solo describe la intención.
        #     Requiere un SETTExecutor con un handler registrado para
        #     "mi_accion" (ver docs/api_reference.md → SETTExecutor).
        #
        # delivery = self.submit_action("mi_accion", payload=resultado)
        # return {**resultado, **delivery}

        return resultado
