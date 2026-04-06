# Resumen del Experimento: Validación Empírica de Physical Reservoir Computing

## Objetivo

Validar empíricamente que un ASIC minero SHA-256 (Lucky Miner LV06 con chip BM1387) puede funcionar como un **reservorio físico** para Reservoir Computing, utilizando el **jitter de timing** de los hashes como estado del reservorio.

## Propiedades Validadas

1. **Echo State Property (ESP)**: El reservorio debe tener memoria de estados previos
2. **Fading Memory**: La influencia de entradas pasadas debe decaer con el tiempo
3. **Separation Property**: Diferentes entradas deben producir diferentes estados
4. **Capacidad Computacional**: Validada mediante benchmark NARMA-10

## Arquitectura del Sistema

```
┌─────────────────┐
│  LV06 Miner     │  (BM1387 ASIC, WiFi)
│  (Hardware)     │
└────────┬────────┘
         │ Stratum Protocol (port 3333)
         ▼
┌─────────────────┐
│ chronos_bridge  │  (Stratum Server)
│   .py           │  - Recibe shares del minero
└────────┬────────┘  - Captura timestamps de llegada
         │ API (port 4029)
         ▼
┌─────────────────┐
│  Experiment     │  (Reservoir Computing)
│  Empirical_...  │  - Obtiene timestamps reales
│   .py           │  - Extrae estado del reservorio
└─────────────────┘  - Entrena readout lineal (Ridge)
                      - Valida con NARMA-10
```

## Cambios Realizados

### 1. Bridge (`chronos_bridge.py`)

**Mejoras implementadas:**
- ✅ Nuevo buffer `share_timestamps` para almacenar timestamps individuales
- ✅ Conversión de nanosegundos a segundos para compatibilidad
- ✅ Nueva API `GET_SHARE_TIMESTAMPS` que expone timestamps reales
- ✅ Buffer circular con límite de 10,000 timestamps

**API nueva:**
```python
# Enviar: "GET_SHARE_TIMESTAMPS"
# Recibe: Lista de timestamps en segundos (float)
```

### 2. Experimento (`Empirical_Validation_Physical_Reservoir_Computing.py`)

**Cambios principales:**
- ✅ Eliminada dependencia de comunicación serial
- ✅ Nueva interfaz `LuckMinerInterface` que usa el bridge
- ✅ Monitor `BridgeShareMonitor` actualizado para usar timestamps reales
- ✅ Manejo robusto de errores y verificaciones de conectividad
- ✅ Visualización mejorada con gráficos y métricas detalladas

**Características:**
- Captura timestamps reales desde el bridge (no simulación)
- Estado del reservorio basado en intervalos de tiempo entre shares
- Vector de estado incluye: deltas, diferencias de deltas, estadísticas
- Entrenamiento con Ridge Regression
- Validación mediante NRMSE en tarea NARMA-10

## Cómo Ejecutar el Experimento

### Paso 1: Configurar el Miner

```bash
# Configurar pool para apuntar al bridge (PC IP: 192.168.0.11)
python configure_lv06.py --miner-ip 192.168.0.15 --pc-ip 192.168.0.11

# O manualmente en la web UI del minero (http://192.168.0.15):
# Pool 1:
#   URL:      stratum+tcp://192.168.0.11:3333
#   User:     chimera
#   Password: x
```

### Paso 2: Iniciar el Bridge

```bash
# En Terminal 1
python chronos_bridge.py
```

**Debes ver:**
```
⏳ CHRONOS LISTENER OPENED on 0.0.0.0:3333
🔗 API LISTENING on 4029
📊 TELEMETRY ENGINE STARTED
⚡ ASIC CONNECTED: 192.168.0.15
⚡ SENDING WAKE-UP SIGNAL: 400MHz
..........  (shares arriving)
```

### Paso 3: Ejecutar el Experimento

```bash
# En Terminal 2
python Empirical_Validation_Physical_Reservoir_Computing.py
```

**Duración:** ~20 minutos (1200 segundos por defecto)

**Salida esperada:**
```
======================================================================
Luck Miner LV06 Reservoir Computing Experiment
======================================================================

⚠️  PREREQUISITES:
   1. Start chronos_bridge.py in a separate terminal
   2. Ensure LV06 miner is connected and hashing
   3. Wait for bridge to show: ⚡ ASIC CONNECTED
   4. You should see share arrivals: ..........

✅ Bridge connection confirmed
📊 Monitoring bridge for share arrivals (using real timestamps)...
🔄 Collecting reservoir states...
   (This will take approximately 20.0 minutes)
   
[... progreso ...]

✅ Data collection complete
📈 Data Statistics:
   Total samples collected: 12000
   State vector dimension: 22
   Samples after washout: 11800

🎓 Training linear readout...
📊 Evaluating performance...

======================================================================
RESULTS
======================================================================
   NRMSE: 0.XXXX
   Baseline (random): 1.XXXX
   Improvement over baseline: XX.X%
======================================================================
```

## Interpretación de Resultados

### Criterios de Éxito

- **NRMSE < 0.3**: ✅ **CONFIRMADO** - El reservorio demuestra capacidad computacional clara
- **0.3 ≤ NRMSE < 0.5**: ⚠️ **Confirmación parcial** - Capacidad moderada
- **NRMSE ≥ 0.5**: ❌ **NO confirmado** - Capacidad insuficiente

### Métricas Clave

1. **NRMSE (Normalized Root Mean Square Error)**
   - Error normalizado entre predicción y target
   - Menor es mejor (0 = perfecto, 1+ = peor que baseline)

2. **Mejora sobre Baseline**
   - Comparación con permutación aleatoria
   - Debe ser positiva para considerar éxito

3. **Dimension del Estado**
   - Por defecto: `window * 2 + 2` (donde window=10)
   - Incluye: deltas, diff(deltas), mean, std

## Parámetros Configurables

### En `Empirical_Validation_Physical_Reservoir_Computing.py`:

```python
BRIDGE_API_HOST = "127.0.0.1"      # IP del bridge
BRIDGE_API_PORT = 4029              # Puerto del bridge
MEASUREMENT_INTERVAL = 0.1          # Intervalo de muestreo (segundos)
EXPERIMENT_DURATION = 1200          # Duración total (segundos)
WASHOUT = 200                       # Período de calentamiento (muestras)
RIDGE_ALPHA = 1e-6                  # Regularización Ridge
```

### En `LuckMinerInterface.get_state()`:

```python
window = 10  # Número de intervalos de tiempo a usar
```

## Requisitos

### Hardware
- Lucky Miner LV06 (BM1387 ASIC)
- Fuente de alimentación (5V/12V)
- Conexión WiFi

### Software
- Python 3.7+
- Dependencias:
  ```bash
  pip install numpy scikit-learn matplotlib scipy
  ```

### Red
- LV06 y PC en la misma red WiFi
- Bridge accesible en `127.0.0.1:4029` (localhost, mismo PC)
- Pool del minero configurado para apuntar al bridge en `192.168.0.11:3333`
- **PC IP actual:** `192.168.0.11`

## Troubleshooting

### Problema: "Cannot connect to bridge"
**Solución:** Asegúrate de que `chronos_bridge.py` esté corriendo antes del experimento.

### Problema: "Insufficient data collected"
**Solución:** 
- Verifica que el minero esté hasheando activamente
- Debes ver dots ("...") en la salida del bridge
- Verifica conexión del pool: `curl http://192.168.0.15/api/system/info`
- Asegúrate que el pool apunte a: `stratum+tcp://192.168.0.11:3333`

### Problema: NRMSE muy alto (>1.0)
**Solución:**
- Aumenta `EXPERIMENT_DURATION` para más datos
- Reduce `MEASUREMENT_INTERVAL` para mayor resolución
- Verifica que el minero esté estable (temperatura, frecuencia)

### Problema: No hay shares llegando
**Solución:**
- Verifica configuración del pool
- Revisa logs del bridge
- Ejecuta `test_connection.py` para diagnóstico

## Próximos Pasos

### Mejoras Futuras

1. **Inyección de Entrada**
   - Modificar dificultad/frecuencia según input
   - Usar `SET_VOLTAGE` y `SET_FREQUENCY` para modulación

2. **Validación de Propiedades**
   - Experimentos específicos para ESP
   - Análisis de fading memory
   - Pruebas de separation property

3. **Optimización de Parámetros**
   - Tuning del tamaño de ventana
   - Optimización de regularización Ridge
   - Selección de features del estado

## Referencias

- **NARMA-10**: Tarea benchmark estándar para Reservoir Computing
- **Reservoir Computing**: Framework computacional usando sistemas dinámicos
- **Echo State Networks**: Tipo específico de Reservoir Computing

---

**Autor:** Francisco Angulo de Lafuente  
**Fecha:** 2025-12-18  
**Versión:** 1.0

