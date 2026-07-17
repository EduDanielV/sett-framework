# Plantillas

Punto de partida para crear tu propio agente y expertos. Copiá,
renombrá, completá los `TODO`. Las dos plantillas, tal como están,
son código real — se pueden instanciar y correr sin completar nada,
así que si algo falla apenas las copiás, el problema es del import,
no de la plantilla.

## Orden recomendado

1. Copiá `expert_template.py` una vez por cada tarea puntual que tu
   dominio necesite resolver (uno, dos, cinco — el número lo define
   tu dominio, no una regla fija).
2. Copiá `agent_template.py` una vez, registrá ahí los expertos que
   escribiste en el paso 1.
3. Elegí, dentro del `process()` del agente, **una** de las tres
   formas de cerrarlo — están explicadas en el propio archivo. Regla
   rápida:
   - ¿Tu agente solo informa un estado? → opción (A).
   - ¿Ejecuta algo real (mensaje, API) pero estás prototipando rápido?
     → opción (B), `propose_action`.
   - ¿Ejecuta algo real y querés la garantía estructural completa
     (que el agente nunca toque el cliente real)? → opción (C),
     `submit_action` + un `SETTExecutor` con handler registrado.
4. `orchestrator.register_agent(TuAgente())`. Listo.

Para sacar un agente del sistema: no llames a `register_agent()` con
él. No hay nada más que desconectar.

Para la explicación completa de cada clase, `docs/api_reference.md`.
Para entender el porqué de las tres capas de riesgo y el filtro ético,
`docs/concepts.md`.
