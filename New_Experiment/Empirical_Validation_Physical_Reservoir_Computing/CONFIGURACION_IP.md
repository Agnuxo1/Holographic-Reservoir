# Configuración de IP para el Experimento

## IPs del Sistema

- **PC IP:** `192.168.0.11`
- **LV06 Miner IP:** `192.168.0.15` (típico, puede variar)
- **Bridge API:** `127.0.0.1:4029` (localhost, mismo PC)
- **Bridge Stratum:** `192.168.0.11:3333` (IP del PC, puerto Stratum)

## Configuración Rápida

### 1. Verificar IP del PC

```bash
# Windows
ipconfig | findstr "IPv4"

# Linux/Mac
ip addr show | grep inet
# o
ifconfig | grep inet
```

**Actual:** `192.168.0.11`

### 2. Configurar Pool del Miner

El miner debe apuntar al bridge que corre en el PC:

```bash
# Método automático
python configure_lv06.py --miner-ip 192.168.0.15 --pc-ip 192.168.0.11

# Método manual (Web UI: http://192.168.0.15)
Pool 1:
  URL:      stratum+tcp://192.168.0.11:3333
  User:     chimera
  Password: x
```

### 3. Verificar Configuración

```bash
# Verificar que el miner puede alcanzar el PC
ping 192.168.0.11

# Verificar pool configurado
curl http://192.168.0.15/api/system/info

# Verificar que el bridge está escuchando
netstat -an | findstr ":3333"
```

## Flujo de Conexión

```
┌─────────────────┐
│  LV06 Miner     │  IP: 192.168.0.15
│  (Hardware)     │
└────────┬────────┘
         │ stratum+tcp://192.168.0.11:3333
         │ (Pool configurado en miner)
         ▼
┌─────────────────┐
│  Bridge         │  Escucha en: 0.0.0.0:3333
│  (PC)           │  API en: 127.0.0.1:4029
│  IP: 192.168.0.11│
└────────┬────────┘
         │ GET_SHARE_TIMESTAMPS
         │ (localhost: 127.0.0.1:4029)
         ▼
┌─────────────────┐
│  Experimento    │  Ejecuta en: PC (192.168.0.11)
│  (PC)           │  Se conecta a: 127.0.0.1:4029
└─────────────────┘
```

## Notas Importantes

1. **Bridge escucha en 0.0.0.0:3333**: Esto permite conexiones desde cualquier IP de la red (incluido el miner en 192.168.0.15)

2. **Experimento usa localhost (127.0.0.1)**: El experimento se ejecuta en el mismo PC que el bridge, por lo que usa localhost para conectarse

3. **Pool del miner apunta a IP del PC**: El miner necesita usar la IP real del PC (192.168.0.11) porque está en otro dispositivo de la red

4. **Si cambia la IP del PC**: 
   - Actualiza la configuración del pool en el miner
   - O usa `configure_lv06.py` con la nueva IP

## Comandos Útiles

```bash
# Encontrar IP del PC
ipconfig | findstr "IPv4"  # Windows
ip addr show | grep inet    # Linux

# Encontrar IP del miner (router admin o scan)
arp -a | findstr "192.168"  # Windows
nmap -sn 192.168.0.0/24     # Linux/Mac

# Verificar conexión del miner al bridge
# (Desde el PC, verifica que el puerto está abierto)
netstat -an | findstr ":3333 LISTENING"

# Test completo de conectividad
python test_connection.py 192.168.0.15
```

---

**IPs Actuales:**
- PC: `192.168.0.11`
- Miner: `192.168.0.15` (verificar si cambia)

