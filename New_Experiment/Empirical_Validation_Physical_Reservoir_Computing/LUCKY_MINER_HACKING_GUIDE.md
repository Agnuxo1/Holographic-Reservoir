# Hacking Lucky Miner LV06 (Unlock Power & Control)

**Objective**: Install Open Source Firmware (AxeOS) to unlock full frequency control (25W+) and bypass stock limitations.

## Findings
The **Lucky Miner LV06** is a hardware clone of the open-source **Bitaxe Ultra**.
- **Stock Firmware**: Restricted, closed source, filters "low difficulty" (causing the 1.4W idle issue).
- **The Hack**: Flash **AxeOS (ESP-Miner)**. This is the "God Mode" firmware used by the community.

## Risks
- **Bricking**: Possible if power fails during flash.
- **Warranty**: Voided (obviously).
- **Recovery**: You can unbrick it using a USB-TTL adapter if it fails.

## "The Hack" Procedure (AxeOS)

### 1. Download Firmware
Go to the official repository:
- **Repo**: [https://github.com/skot/ESP-Miner](https://github.com/skot/ESP-Miner) (Original)
- **Repo**: [https://github.com/matlen67/LuckyMiner-LV06](https://github.com/matlen67/LuckyMiner-LV06) (Specific for LV06)

**Files needed**: `esp-miner.bin` and `www.bin`.

### 2. Flash (Web Method - Easiest)
1. Find your miner's IP address.
2. Go to `http://<MINER_IP>/update` (or look for "OTA Update" in the menu).
3. Upload the `.bin` file.

### 3. Flash (Cable Method - If Bricked)
You will need a USB-C cable or a flasher tool (ESP-Prog) if the web interface is locked.
- Use **ESP-Tool** or the web-based installer at [https://bitaxe.org/](https://bitaxe.org/).

## Expected Gains
- **Power**: Unlock full 25W consumption (by setting frequency > 500 MHz).
- **Telemetry**: Real-time voltage/freq stats.
- **Efficiency**: Better tuning (J/TH).

**Recommendation**: Attempt the **Web OTA Update** first with `ESP-Miner` from the Skot repo. It is the gold standard.
