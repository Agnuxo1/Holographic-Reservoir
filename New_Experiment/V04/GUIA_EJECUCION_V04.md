# GUÍA DE EJECUCIÓN V04: EXPERIMENTO DE MODULACIÓN DE VOLTAJE

## Estado del Sistema
- ✅ **chronos_bridge.py**: CORREGIDO (faltaba import entropy, inicialización pending_voltage)
- ✅ **exp_01_voltage_modulation.py**: MEJORADO (validación de conexión añadida)
- ✅ **Objetivo**: Obtener datos reales del BM1387 (LV06) para análisis de modulación de voltaje

---

## Requisitos Previos

### Hardware
- **Lucky Miner LV06** con chip BM1387 (mismo chip que Antminer S9)
- Conectado a la misma red que la PC de control
- AxeOS firmware funcionando

### Software
```bash
pip install numpy scipy
```

### Configuración del LV06
1. Accede a la interfaz web del LV06: `http://192.168.0.15` (o la IP de tu miner)
2. Configura el pool:
   - **URL**: `<IP_DE_TU_PC>:3333` (ejemplo: `192.168.0.14:3333`)
   - **Usuario**: cualquier cosa (ejemplo: `chimera`)
   - **Password**: cualquier cosa

---

## PASO 1: Iniciar el Chronos Bridge

El bridge actúa como servidor Stratum y recolecta datos temporales del ASIC.

```bash
cd "d:\Holographic Reservoir Computing\V04"
python drivers/chronos_bridge.py
```

### Salida Esperada:
```
⏳ CHRONOS LISTENER OPENED on 0.0.0.0:3333
🔗 API LISTENING on 4029
📊 TELEMETRY ENGINE STARTED
```

### Esperar Conexión del Miner:
Cuando el LV06 se conecte, verás:
```
⚡ ASIC CONNECTED: ('192.168.0.15', 54321)
⚡ SENDING WAKE-UP SIGNAL: 400MHz
```

### Verificar Flujo de Shares:
Deberías ver puntos apareciendo en la consola:
```
..........
📊 RITMO: CV=0.8523 | Entropía Temporal=2.1456
```

**IMPORTANTE:** Deja esta terminal abierta. El bridge debe correr continuamente.

---

## PASO 2: Verificar Telemetría (Opcional pero Recomendado)

Abre una **segunda terminal** para verificar que la telemetría del LV06 funciona:

```bash
cd "d:\Holographic Reservoir Computing\V04"
python -c "
import socket, json
s = socket.socket()
s.connect(('127.0.0.1', 4029))
s.send(b'GET_METRICS')
data = s.recv(4096).decode()
print(json.dumps(json.loads(data), indent=2))
s.close()
"
```

### Salida Esperada:
```json
{
  "cv": 0.8523,
  "time_entropy": 2.1456,
  "timestamp": 1702950123.45,
  "voltage": 990,
  "power": 45,
  "temp": 65,
  "freq": 400,
  "hashrate": 500
}
```

Si ves `"timestamp": 0` o todos los valores en 0, **espera más tiempo** (el miner tarda ~30s en estabilizarse).

---

## PASO 3: Ejecutar el Experimento de Modulación de Voltaje

Abre una **tercera terminal** (o cierra la de verificación):

```bash
cd "d:\Holographic Reservoir Computing\V04"
python experiments/exp_01_voltage_modulation.py
```

### Proceso del Experimento:

#### 3.1. Validación Automática
El experimento primero valida la conexión:
```
=== V04: VOLTAGE MODULATION EXPERIMENT ===

🔍 VALIDATING BRIDGE CONNECTION...
   ✅ Bridge Active: CV=0.8523, Last Update=1702950123.45

✅ VALIDATION PASSED - Starting Experiment
```

Si la validación falla, verás instrucciones de troubleshooting.

#### 3.2. Prueba de Cada Voltaje (4 voltajes × ~3 minutos = 12 minutos total)

**Para cada voltaje (990mV, 950mV, 900mV, 850mV):**

1. **Inyección de Voltaje**:
   ```
   --- TESTING VOLTAGE: 990mV ---
   💊 Dosing Voltage: 990mV...
   ⏳ Waiting 60s for Miner Reboot/Stabilization...
   ```
   - El bridge envía comando HTTP PATCH al LV06
   - El miner se reinicia automáticamente (tarda ~40s)
   - **IMPORTANTE**: El miner se desconectará y reconectará durante este tiempo

2. **Test 1: Noise (Control)**:
   ```
   ⏳ Monitoring (25s)....................
   ```
   - Inyecta seed "Chaos and Entropy"
   - Monitorea CV durante 25 segundos
   - Cada punto (`.`) = 1 lectura de métricas

3. **Test 2: Structure (Target)**:
   ```
   ⏳ Monitoring (25s)....................
   ```
   - Inyecta seed "Structure and Order (Shakespeare)"
   - Monitorea CV durante 25 segundos

**Tiempo total por voltaje**: ~1.5 minutos (60s espera + 25s noise + 25s structure)

---

## PASO 4: Analizar los Resultados

### 4.1. Tabla de Resumen (en Terminal)
Al finalizar, verás:
```
SUMMARY TABLE:
Volt   | CV Noise   | CV Struct  | Delta
990    | 1.1234     | 0.8765     | 0.2469
950    | 1.0987     | 0.8321     | 0.2666
900    | 0.9876     | 0.7654     | 0.2222
850    | 0.8765     | 0.6543     | 0.2222
```

### 4.2. Reporte Markdown Generado
```
✅ Report Saved: docs/REPORT_VOLTAGE_MODULATION.md
```

Abre el archivo generado:
```bash
notepad "d:\Holographic Reservoir Computing\V04\docs\REPORT_VOLTAGE_MODULATION.md"
```

---

## INTERPRETACIÓN DE RESULTADOS

### Coeficiente de Variación (CV):
- **CV < 0.5**: 💎 **Crystal State** (Metronomic, orden extremo)
- **CV ~ 0.7-0.9**: 💧 **Viscous** (Líquido, orden moderado)
- **CV ~ 1.0**: 🎲 **Poisson** (Aleatorio puro)
- **CV > 1.1**: 🔥 **Bursty/Chaotic** (Explosiones de actividad)

### Delta (CV_Noise - CV_Struct):
- **Delta > 0.2**: Sistema **sensible** a seeds semánticos
- **Delta < 0.1**: Sistema **insensible** (voltaje demasiado bajo o alto)
- **Delta < 0**: Contradicción (puede indicar ruido térmico excesivo)

### Hipótesis del Experimento:
> **Voltaje Bajo → Menos Ruido Térmico → CV más bajo (Orden)**

**Predicción:**
- 990mV: CV alto (caos térmico)
- 850mV: CV bajo (orden, "sedación del silicio")

---

## TROUBLESHOOTING

### Problema 1: "Bridge API Error (GET_METRICS)"
**Causa**: chronos_bridge no está corriendo
**Solución**: Ejecuta `python drivers/chronos_bridge.py` en otra terminal

### Problema 2: "CV = 0.0000" en todos los voltajes
**Causa**: El miner no está conectado o no envía shares
**Diagnóstico**:
1. Verifica que el bridge muestre `⚡ ASIC CONNECTED`
2. Verifica que veas puntos (`....`) apareciendo (son shares)
3. Revisa la configuración del pool en el LV06

### Problema 3: "Miner desconectado" durante el experimento
**Causa**: El cambio de voltaje reinicia el miner
**Solución**: Es normal. El experimento espera 60s para que el miner se reconecte.
- Si no se reconecta tras 60s, verifica la configuración del pool

### Problema 4: HTTP ERROR al cambiar voltaje
**Causa**: La API del LV06 no responde o requiere autenticación
**Diagnóstico**:
1. Verifica que puedes acceder a `http://192.168.0.15/api/system/info` desde el navegador
2. Si el firmware requiere autenticación, actualiza la función `set_voltage()` en chronos_bridge.py

### Problema 5: "timestamp": 0 en métricas
**Causa**: El miner aún no ha enviado suficientes shares para calcular CV
**Solución**: Espera ~30-60 segundos y vuelve a verificar

---

## PRÓXIMOS PASOS TRAS OBTENER DATOS

### 1. Análisis Estadístico
```python
import pandas as pd

# Crear DataFrame desde el reporte
data = {
    'voltage': [990, 950, 900, 850],
    'cv_noise': [1.12, 1.09, 0.98, 0.87],
    'cv_struct': [0.87, 0.83, 0.76, 0.65],
    'delta': [0.25, 0.26, 0.22, 0.22]
}
df = pd.DataFrame(data)

# Correlación voltaje vs CV
correlation = df['voltage'].corr(df['cv_struct'])
print(f"Correlación Voltaje-CV: {correlation:.4f}")
```

### 2. Gráficos (Opcional)
```python
import matplotlib.pyplot as plt

plt.figure(figsize=(10, 5))
plt.plot(df['voltage'], df['cv_noise'], 'o-', label='CV Noise', linewidth=2)
plt.plot(df['voltage'], df['cv_struct'], 's-', label='CV Structure', linewidth=2)
plt.xlabel('Voltage (mV)')
plt.ylabel('Coefficient of Variation')
plt.title('Voltage Modulation Effect on CV')
plt.legend()
plt.grid(True)
plt.savefig('V04/docs/voltage_cv_plot.png')
plt.show()
```

### 3. Extrapolar a Antminer S9
El LV06 y el S9 usan el **mismo chip BM1387**, por lo que:
- **Comportamiento cualitativo**: Idéntico (mismo rango de voltaje, misma física)
- **Velocidad**: S9 tiene ~180 chips vs 1 chip del LV06 → 180× más shares/sec
- **Interpretación**: Los valores de CV serán similares, pero con mejor precisión estadística

---

## NOTAS IMPORTANTES

1. **Cuello de Botella Aceptado**:
   - V04 opera a ~0.15 shares/sec (lento)
   - Es suficiente para obtener datos reales del BM1387
   - La latencia NO afecta la validez de las métricas temporales (CV)

2. **Paciencia Requerida**:
   - Experimento completo: ~12 minutos
   - Cada cambio de voltaje reinicia el miner (60s)
   - Es normal que el progreso sea lento

3. **Datos Reales = Datos Valiosos**:
   - Aunque sea lento, son datos 100% del hardware BM1387
   - Estos datos son extrapolables al S9
   - No hay contaminación de `os.urandom()` (V03 garantiza pureza)

---

## CHECKLIST PRE-EJECUCIÓN

- [ ] LV06 encendido y conectado a la red
- [ ] Pool configurado en LV06: `<IP_PC>:3333`
- [ ] `numpy` y `scipy` instalados
- [ ] Terminal 1: `python drivers/chronos_bridge.py` corriendo
- [ ] Terminal 1: Muestra `⚡ ASIC CONNECTED`
- [ ] Terminal 1: Aparecen puntos (`....`) periódicamente
- [ ] Verificación: `GET_METRICS` retorna `timestamp > 0`
- [ ] Terminal 2: Listo para ejecutar experimento

---

## CONTACTO Y SOPORTE

Si encuentras problemas no cubiertos en esta guía, revisa:
1. [V03/README_V3.md](../V03/README_V3.md) - Documentación del sistema base
2. [V03/docs/COMPARATIVE_ANALYSIS.md](../V03/docs/COMPARATIVE_ANALYSIS.md) - Filosofía del diseño
3. Logs de chronos_bridge (Terminal 1) - Busca errores HTTP o conexión

---

**Última Actualización**: 2025-12-18
**Versión**: V04 (Voltage Modulation Experiment)
**Estado**: ✅ LISTO PARA EJECUCIÓN
