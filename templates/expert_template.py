"""
templates/expert_template.py
==============================
Copiá este archivo, renombralo, y completá las tres partes marcadas con
TODO. Un experto resuelve UNA sola tarea — si te encontrás queriendo
hacer dos cosas distintas acá adentro, probablemente necesitás dos
expertos, no uno más grande.

No registres este experto en ningún lado vos mismo — eso lo hace el
agente que lo contiene, con self.register_expert(...). Ver agent_template.py.
"""
from __future__ import annotations
from typing import Any

from sett import SETTExpert


# TODO: renombrá la clase con el nombre de tu tarea específica
# (ej: HeartRateExpert, WeatherLookupExpert, IntentClassifierExpert)
class MyExpert(SETTExpert):
    """
    TODO: una línea describiendo QUÉ tarea puntual resuelve este experto.
    Ejemplo: "Evalúa la frecuencia cardíaca contra rangos de referencia."
    """

    def resolve(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Acá vive toda la lógica de este experto. Se llama siempre desde
        el agente dueño, nunca directamente desde afuera.

        Args:
            context: los datos que el agente le pasó (input_data, u
                     otro dict armado por el propio agente).

        Returns:
            Un dict con el resultado de este experto. El agente lo va
            a combinar con el resultado de otros expertos, si tiene más.
        """

        # 1. TODO — leé lo que necesites de `context`
        # valor = context.get("mi_dato_esperado")

        # 2. TODO — hacé el cálculo/lógica puntual de este experto
        # resultado = mi_logica(valor)

        # 3. (opcional) si otro experto de este mismo agente va a
        #    necesitar este dato después, guardalo en memoria privada.
        #    Nadie fuera de este agente puede leerla — ni el
        #    orquestador, ni otros agentes.
        # if self._private_memory:
        #     self._private_memory.write("mi_clave", resultado)

        # 4. TODO — devolvé el resultado como dict
        return {}
