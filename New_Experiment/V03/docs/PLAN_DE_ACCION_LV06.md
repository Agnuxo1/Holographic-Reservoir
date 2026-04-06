# PLAN DE ACCIÓN: Optimización de Infraestructura CHIMERA (LV06)

**Objetivo**: Alcanzar 500 GH/s de flujo de entropía real (aprox. 116 shares/segundo) utilizando el hardware Lucky Miner LV06.

## 1. Diagnóstico del Problema Actual
Las pruebas arrojaron 0.03 shares/segundo. Esto confirma que el hardware no está limitado físicamente, sino **lógicamente**.
- **Causa Probable A**: El minero ignora la instrucción `mining.set_difficulty` debido a un formato no estándar en la negociación Stratum.
- **Causa Probable B**: El "Target" definido en el trabajo (`nBits`) contradice la dificultad baja, y el chip ASIC descarta internamente los resultados "débiles" antes de enviarlos.

## 2. Estrategia: "CHIMERA Driver Framework"
Abandonaremos los scripts de prueba simples (`wifi_bridge`) para construir un **Driver Nativo Robusto**.

### Componentes del Framework
1.  **Nucleo AsyncIO**: Reemplazo de `threading` por `asyncio` para manejar cientos de eventos por segundo sin bloqueo.
2.  **Gestor de Protocolo Estricto (Stratum Compliance)**:
    - Negociación explícita de capacidades (`mining.configure`).
    - **Forzado de Target (nBits)**: Manipularemos el campo `nBits` del encabezado del bloque para que coincida físicamente con la dificultad 1 (o menor), engañando al firmware para que acepte basura como válida.
3.  **Modo "Flood"**: Envío proactivo de trabajos (`clean_jobs=True`) cada 500ms para evitar que el minero entre en estado "Idle" esperando a que se resuelva un bloque difícil.

## 3. Hoja de Ruta (Pasos Inmediatos)

### FASE 1: Prototipo de Driver (`chimera_driver.py`)
- [ ] Implementar servidor Stratum básico con `asyncio`.
- [ ] Añadir selector de dificultad dinámica.
- [ ] **Crucial**: Implementar cálculo correcto de `nBits` basado en dificultad deseada.
    - *Si Diff=1 -> nBits=0x1d00ffff*
    - *Si Diff=0.1 -> Recalcular nBits para target más alto (más fácil).*

### FASE 2: Stress Test (Inundación)
- [ ] Ejecutar el driver y monitorizar en tiempo real.
- [ ] Ajustar `nBits` hasta ver la "cascada" de shares.

### FASE 3: Integración
- [ ] Conectar el flujo de salida del driver directamente al Reservorio Holográfico.

## Acción Requerida
Procederé inmediatamente con la **FASE 1**: Crear `chimera_driver.py` con lógica avanzada de `nBits` para desbloquear el ASIC.
