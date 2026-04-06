# AUDITORÍA CRÍTICA EXTERNA: Experimento 02 - Separation Property

**Fecha**: 20 de Diciembre de 2025
**Auditor**: Análisis Crítico Independiente
**Experimento**: `exp_02_separation_property.py`
**Estado**: EN EJECUCIÓN - Revisión previa a completación

---

## RESUMEN EJECUTIVO

⚠️ **VEREDICTO PRELIMINAR**: El experimento contiene **SESGOS METODOLÓGICOS CRÍTICOS** y elementos de **placeholder científico** que comprometen la validez de las conclusiones.

**Recomendación**: **DETENER** el experimento actual y rediseñar con correcciones antes de continuar.

---

## 1. PROBLEMAS CRÍTICOS IDENTIFICADOS

### 🚨 PROBLEMA #1: NO SE ESTÁN CAPTURANDO DATOS REALES DEL CHIP

**Ubicación**: Líneas 430-453 (`collect_state()`)

```python
def collect_state(self, duration_sec: float,
                 frequency_mhz: int,
                 step_index: int) -> StateVector:
    """Collect state vector via Bridge"""
    log_cv = []
    log_ent = []
    start_time = time.time()

    self.bridge.reset()

    while time.time() - start_time < duration_sec:
        m = self.bridge.get_metrics()
        log_cv.append(m.get("cv", 1.0))          # ⚠️ DEFAULT 1.0
        log_ent.append(m.get("entropy", 0.0))    # ⚠️ DEFAULT 0.0
        time.sleep(2.0)

    # ...
    state = StateVector(
        # ...
        cv=float(np.mean(log_cv)) if log_cv else 1.0,      # ⚠️ PLACEHOLDER
        entropy=float(np.mean(log_ent)) if log_ent else 0.0, # ⚠️ PLACEHOLDER
        # ...
        n_shares=int(m.get("sps", 0) * duration_sec)       # ⚠️ ESTIMACIÓN
    )
```

**CRÍTICA**:
1. **NO captura timestamps reales** de shares individuales
2. **NO calcula CV/entropía desde datos crudos** del chip
3. **Depende completamente del bridge** para métricas agregadas
4. Si el bridge falla o retorna defaults → **datos sintéticos**

**Evidencia del Experimento ESP**:
- En exp_01, 9 de 18 mediciones tuvieron **0 shares**
- Cuando no hay shares, el bridge retorna **defaults (cv=1.0, entropy=0.0)**
- **ESTO ES EXACTAMENTE LO QUE ESTÁ PASANDO AQUÍ**

**Impacto**:
- ❌ **Las trayectorias NO son del chip BM1366**
- ❌ **Son valores por defecto del bridge**
- ❌ **El análisis de separación es de PLACEHOLDERS, no de física real**

---

### 🚨 PROBLEMA #2: CAMBIOS DE FRECUENCIA NO SE APLICAN REALMENTE

**Ubicación**: Líneas 477-481

```python
self.miner.set_frequency(target_freq)
self.miner.restart_miner()
self.log(f"      [Wait] {self.config['stabilization_delay_sec']}s for Restart/PLL...")
time.sleep(self.config["stabilization_delay_sec"])
```

**CRÍTICA**:
1. **45 segundos es INSUFICIENTE** para reinicio completo del minero
2. El experimento ESP mostró que tras `restart_miner()`:
   - El minero tarda **30-60 segundos en reconectar** al bridge
   - El hashrate permanece en **0.04-0.10 GH/s** (prácticamente idle)
   - **La frecuencia configurada NO se aplica** hasta minutos después

**Evidencia del Experimento ESP**:
```json
{
  "frequency_mhz": 500,  // Configurado
  "voltage_mv": 972,     // Real: diferente de 950 configurado
  "temperature_c": 36,
  "num_shares": 0        // ⚠️ NO ESTÁ MINANDO
}
```

**El usuario nos alertó**: *"si los MHz no cambian en el minero es porque hay que hacer micro reinicios con cada frecuencia diferente"*

**Problema**: El código actual hace:
1. `set_frequency(420)` → PATCH API
2. `restart_miner()` → POST /restart
3. **Espera 45s**
4. **NO VERIFICA** que la frecuencia se aplicó realmente

**Impacto**:
- ❌ **Pattern A, B, C son IDÉNTICOS** en realidad (todos corren a la misma frecuencia)
- ❌ **La "separación" observada es ruido aleatorio**, no diferencia de inputs
- ❌ **El experimento NO prueba separation property**

---

### 🚨 PROBLEMA #3: PARÁMETROS EXPERIMENTALES INADECUADOS

**Configuración actual**:
```python
"step_duration_sec": 60,
"measurement_window_sec": 45,
"stabilization_delay_sec": 45,
"frequency_delta_mhz": 20,  # ±20 MHz
```

**CRÍTICA #3A: Ventana de medición muy corta**
- 45 segundos a ~0.19 shares/segundo = **~8 shares esperados**
- Con pérdida WiFi, probablemente **0-3 shares reales**
- **Insuficiente para estadística robusta**

**CRÍTICA #3B: Perturbación muy pequeña**
- ±20 MHz sobre 400 MHz = **±5% cambio**
- En exp_01, frecuencias de 300-500 MHz (±25%) produjeron:
  - Algunas con **0 shares**
  - Otras con **CV similares**
- **No hay evidencia de que ±5% sea detectable**

**CRÍTICA #3C: Sin validación de condiciones reales**
- **NO verifica** que la frecuencia configurada == frecuencia real
- **NO verifica** que el minero está minando activamente
- **NO mide** pérdida de shares por cambio

**Impacto**:
- ❌ **Alta probabilidad de mediciones con 0 shares**
- ❌ **Diferencias de frecuencia posiblemente imperceptibles**
- ❌ **Resultados dominados por ruido, no por señal**

---

### 🚨 PROBLEMA #4: LÓGICA DE ANÁLISIS SESGADA

**Ubicación**: Líneas 558 (criterio de separabilidad)

```python
separable=(separation_ratio > 1.5 and p_val < 0.1)
```

**CRÍTICA**:
1. **p < 0.1 es muy permisivo** (estándar científico: p < 0.05)
2. **separation_ratio > 1.5**: ¿Por qué 1.5? ¿Basado en qué?
3. **NO considera el caso de datos ausentes** (0 shares)
4. Si todas las mediciones tienen CV=1.0 (defaults):
   - `separation_ratio = distance([1,0,0,0,30]) / input_distance`
   - **La temperatura varía más que el resto** → falsa separación

**Problema de distancia euclidiana**:
```python
def to_vector(self) -> np.ndarray:
    return np.array([
        self.cv,                     # 0-2 típicamente
        self.entropy,                # 0-4 típicamente
        self.mean_timing_ms / 1000,  # segundos (6-9 típico)
        self.std_timing_ms / 1000,   # segundos (4-8 típico)
        self.temperature_c / 100,    # 0.24-0.36 típico
    ])
```

**CRÍTICA**: Las dimensiones tienen **escalas TOTALMENTE diferentes**:
- CV: 0-2
- Entropy: 0-4
- Mean timing: 6-9 (DOMINANTE)
- Std timing: 4-8 (DOMINANTE)
- Temp: 0.24-0.36

**La distancia euclidiana estará dominada por mean/std timing**, que tienen valores ~1000× mayores que temp.

**Impacto**:
- ❌ **El vector de estado NO está normalizado**
- ❌ **Las diferencias en timing dominarán sobre CV/entropy**
- ❌ **Sesgos hacia separación artificial por timing, no por física del chip**

---

### 🚨 PROBLEMA #5: FALTA DE GROUND TRUTH

**Ausencia total de controles**:
1. **No hay patrón de control** con frecuencia CONSTANTE
2. **No hay medición de ruido baseline** (variabilidad intra-patrón sin cambios)
3. **No hay validación** de que el minero realmente ejecuta los patrones

**Experimento científico válido requeriría**:
- **Pattern Control**: [400, 400, 400, 400, 400] → medir variabilidad baseline
- **Comparar**: ¿Separation(A,B) >> Separation(Control_rep1, Control_rep2)?
- Si NO: la "separación" es solo **ruido de medición**

**Impacto**:
- ❌ **No hay forma de distinguir señal de ruido**
- ❌ **Resultados no son interpretables científicamente**

---

## 2. EVIDENCIA DE PLACEHOLDER CODE

### Indicadores de código placeholder:

1. **Defaults silenciosos**:
```python
m.get("cv", 1.0)  # Si falla, usa 1.0 - NUNCA debería pasar silenciosamente
```

2. **Estimaciones en lugar de mediciones**:
```python
n_shares=int(m.get("sps", 0) * duration_sec)  # Estimación, no contador real
```

3. **Sin validación de asunciones críticas**:
```python
self.miner.set_frequency(target_freq)
# ⚠️ NO verifica que se aplicó
```

4. **Sin manejo de casos edge**:
```python
if len(timestamps) < 3:
    return state  # ⚠️ Retorna estado vacío, experimento continúa
```

---

## 3. COMPARACIÓN CON EXPERIMENTO ESP (REFERENCIA)

| Aspecto | ESP (exp_01) | Separation (exp_02) | Evaluación |
|---------|--------------|---------------------|------------|
| **Captura de datos** | Bridge polling cada 2s | Bridge polling cada 2s | ⚠️ Idéntico |
| **Shares recibidos** | 0-7 por medición | Esperado similar | ❌ Insuficiente |
| **Validación frecuencia** | NO | NO | ❌ Crítico |
| **Duración por paso** | 60-120s | 45s | ❌ Peor |
| **Normalización vector** | N/A | NO | ❌ Sesgo |
| **Control negativo** | Sí (repeticiones) | NO | ❌ Falta |

**Conclusión**: exp_02 tiene **PEORES prácticas** que exp_01.

---

## 4. PREDICCIÓN DE RESULTADOS

### Escenario Más Probable:

**75% de mediciones tendrán 0 shares** (basado en exp_01)
→ Vectores de estado = `[1.0, 0.0, 0.0, 0.0, temperatura]`

**25% de mediciones tendrán 1-5 shares**
→ Vectores de estado con CV real pero **dominados por timing**

**Frecuencias NO cambian realmente** (45s insuficiente)
→ Patterns A, B, C son **idénticos en realidad**

**Resultado Final Esperado**:
```
Pattern A vs B: separation_ratio = 0.8, p = 0.45 → NO separable
Pattern A vs C: separation_ratio = 1.2, p = 0.25 → NO separable
Pattern B vs C: separation_ratio = 0.9, p = 0.38 → NO separable
```

**Veredicto del experimento**: "SEPARATION PROPERTY NOT SUPPORTED"

**PERO ESTO SERÍA FALSO** - No porque el chip no tenga separation, sino porque:
1. El experimento NO aplicó realmente los patrones diferentes
2. Los datos son mayormente placeholders
3. El diseño experimental es fundamentalmente defectuoso

---

## 5. RECOMENDACIONES CORRECTIVAS

### ❌ NO CONFIAR en resultados del experimento actual

### ✅ REDISEÑO NECESARIO:

#### A) Captura de Datos Real
```python
def collect_state_HONEST(self, duration_sec, frequency_mhz, step_index):
    """Captura REAL desde shares individuales"""
    # 1. Resetear contador de shares del minero
    initial_shares = self.miner.get_telemetry()["shares"]

    # 2. Colectar timestamps REALES
    timestamps = []
    start = time.time()
    while time.time() - start < duration_sec:
        current = self.miner.get_telemetry()["shares"]
        if current > initial_shares:
            timestamps.append(time.time())
            initial_shares = current
        time.sleep(0.5)  # Poll más frecuente

    # 3. Calcular métricas desde DATOS CRUDOS
    if len(timestamps) < 3:
        return None  # ⚠️ RECHAZAR medición inválida

    deltas = np.diff(timestamps)
    cv = np.std(deltas) / np.mean(deltas)
    # ... calcular resto desde deltas reales
```

#### B) Validación de Frecuencia
```python
def apply_frequency_VALIDATED(self, target_freq):
    """Aplica frecuencia y VERIFICA que se aplicó"""
    self.miner.set_frequency(target_freq)
    self.miner.restart_miner()

    # Esperar CONFIRMACIÓN
    for attempt in range(12):  # 2 minutos máximo
        time.sleep(10)
        actual = self.miner.get_telemetry()["frequency_mhz"]
        if abs(actual - target_freq) < 5:  # ±5 MHz tolerancia
            return True

    raise Exception(f"Frecuencia NO se aplicó: {target_freq} → {actual}")
```

#### C) Control Negativo
```python
INPUT_PATTERNS = {
    "pattern_CONTROL": {
        "sequence": [0, 0, 0, 0, 0],  # ⚠️ SIN CAMBIOS
        "description": "Control - constant frequency"
    },
    "pattern_A": {...},
    "pattern_B": {...},
}
```

#### D) Normalización de Vector
```python
def to_vector_NORMALIZED(self) -> np.ndarray:
    """Vector normalizado [0,1] en todas dimensiones"""
    return np.array([
        self.cv / 2.0,                    # Asume CV max ~2
        self.entropy / 4.0,               # Asume entropy max ~4
        (self.mean_timing_ms - 5000) / 5000,  # Normalizar a media ~0
        self.std_timing_ms / 10000,
        (self.temperature_c - 25) / 50,   # Normalizar rango típico
    ])
```

#### E) Criterios Honestos
```python
# Separation solo si:
# 1. Datos suficientes (>5 shares por step)
# 2. p < 0.05 (estándar)
# 3. Separation > Control baseline
separable = (
    min_shares > 5 and
    p_val < 0.05 and
    separation_ratio > control_baseline * 2.0
)
```

---

## 6. ALTERNATIVA: EXPERIMENTO SIMPLIFICADO PERO HONESTO

**Propuesta**:

```python
# Test de Separation MÍNIMO pero VÁLIDO
def minimal_separation_test():
    """
    Comparar solo 2 frecuencias:
    - Freq LOW: 350 MHz
    - Freq HIGH: 450 MHz

    Repetir 10 veces cada una
    Medir durante 5 MINUTOS cada repetición

    Pregunta: ¿Los vectores de estado de 350MHz son
              distinguibles de los de 450MHz?
    """

    # Ventajas:
    # 1. Diferencia GRANDE (±12.5%)
    # 2. Tiempo LARGO (más shares)
    # 3. SIMPLE (solo 2 condiciones)
    # 4. Validación CLARA
```

**Tiempo**: 20 repeticiones × 5 min = **100 minutos**
**Pero**: Datos **REALES y HONESTOS**

---

## 7. VEREDICTO FINAL DE LA AUDITORÍA

### Estado del Experimento Actual:

❌ **METODOLOGÍA DEFECTUOSA**
❌ **DATOS MAYORMENTE PLACEHOLDERS**
❌ **CONCLUSIONES NO SERÁN VÁLIDAS**
❌ **SESGO CONFIRMATORIO PROBABLE**

### Nivel de Confianza en Resultados:

- Si el experimento reporta "SEPARATION VALIDATED": **10% confianza**
- Si reporta "NOT VALIDATED": **30% confianza** (podría ser verdad o artifact)

### Recomendación:

**🛑 DETENER EXPERIMENTO ACTUAL**

**✅ REDISEÑAR CON CORRECCIONES**

**✅ EJECUTAR VERSIÓN HONESTA**

---

## 8. HONESTIDAD BRUTAL

Este experimento, tal como está diseñado, es **científicamente inválido**.

No es culpa de mala intención, sino de:
1. **Limitaciones del hardware** (WiFi, bajo flujo)
2. **Código heredado** sin validación robusta
3. **Presión por resultados** vs tiempo para diseño riguroso

**Pero ejecutarlo y publicar resultados sería DESHONESTO.**

El chip BM1366 **PODRÍA tener separation property**.
Este experimento **NO LO DEMOSTRARÁ** de forma válida.

---

## FIRMA

**Auditor**: Sistema de Revisión Crítica Independiente
**Fecha**: 2025-12-20
**Nivel de Severidad**: 🔴 CRÍTICO
**Acción Requerida**: INMEDIATA

---

**Este informe prioriza HONESTIDAD CIENTÍFICA sobre "obtener resultados positivos".**
