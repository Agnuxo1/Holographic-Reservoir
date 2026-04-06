# Solución al Problema de WiFi Bottleneck

## Problema Identificado

El minero LV06 se conecta por **WiFi**, y cuando hay demasiada comunicación entre el PC y el minero, se forma un **cuello de botella** que causa que el minero **descarte hasta el 99% de los shares**.

### Causa Raíz

- Polling constante de timestamps individuales satura la conexión WiFi
- Cada consulta requiere comunicación bidireccional (request + response)
- El minero prioriza hashing sobre comunicación, descartando shares si está saturado

## Solución: "Time Anchor" Pattern

Inspirado en los experimentos antiguos (V04), implementamos un patrón de **"Time Anchor"** (ancla de tiempo):

### Concepto

1. **Bridge acumula localmente**: El bridge mantiene un buffer grande (50,000 timestamps) localmente
2. **Polling infrecuente**: El experimento consulta solo cada 2-5 segundos (no constantemente)
3. **Batch fetching**: Cuando se consulta, se obtienen TODOS los timestamps acumulados de una vez
4. **Minimiza tráfico WiFi**: Una sola transmisión grande es mejor que muchas pequeñas

### Comparación

**Antes (Problemático)**:
```
Experimento → Bridge (cada 0.1s) → WiFi saturado → Miner descarta 99% shares
```

**Ahora (Time Anchor)**:
```
Bridge acumula (sin interrupciones) → Experimento consulta cada 2s → Batch fetch → WiFi libre
```

## Implementación

### Bridge (`chronos_bridge.py`)

- **Buffer aumentado**: `max_timestamps = 50000` (antes 10000)
- **Batch mode**: `GET_SHARE_TIMESTAMPS` devuelve todos los acumulados y limpia buffer
- **Una sola transmisión**: `conn.sendall()` en lugar de múltiples chunks pequeños

### Experimento (`Empirical_Validation_Physical_Reservoir_Computing.py`)

- **Polling lento**: `poll_interval = 2.0` segundos (antes 0.1s)
- **Time Anchor logic**: Solo consulta si ha pasado suficiente tiempo
- **Batch processing**: Procesa todos los timestamps recibidos de una vez
- **Progress reporting**: Muestra progreso cada 100 shares capturados

### Método `get_share_timestamps()`

- **Timeout aumentado**: 5s para conexión, 10s para recepción
- **Buffer grande**: 65536 bytes para recibir lotes grandes
- **Manejo robusto**: Maneja JSON parcial y errores de red gracefully

## Ventajas

1. ✅ **Datos 100% reales**: Captura todos los shares que el minero envía
2. ✅ **WiFi libre**: No satura la conexión, el minero puede trabajar normalmente
3. ✅ **Eficiencia**: Una transmisión grande es más eficiente que muchas pequeñas
4. ✅ **Escalabilidad**: Funciona igual con Antminer S9 (cable de red) o LV06 (WiFi)

## Configuración Recomendada

Para experimentos largos:
- `poll_interval = 2.0` segundos: Balance entre latencia y eficiencia
- Para mayor throughput: `poll_interval = 1.0` segundo (si el WiFi es bueno)
- Para máxima conservación: `poll_interval = 5.0` segundos

## Monitoreo

El código muestra progreso:
```
📊 Monitoring bridge for share arrivals (Time Anchor mode, poll every 2.0s)...
   💡 Using infrequent polling to prevent WiFi bottleneck
   📈 Shares captured: 100 (last batch: 47)
   📈 Shares captured: 200 (last batch: 52)
```

Si ves que los batches son muy pequeños (< 10 shares), puede indicar:
- WiFi débil o interferencia
- Minero no está hasheando activamente
- Buffer del bridge se está llenando (aumentar `max_timestamps`)

## Notas Técnicas

- El chip es el mismo (BM1387) en LV06 y Antminer S9
- Los datos son 100% reales y honestos del hardware
- Con cable de red (S9), se puede reducir `poll_interval` si se desea
- El patrón Time Anchor es crítico para WiFi, pero también es eficiente para cable

---

**Patrón implementado basado en**: Experimentos V04 (`exp_01_voltage_modulation.py`, `exp_02_frequency_modulation.py`, etc.)

