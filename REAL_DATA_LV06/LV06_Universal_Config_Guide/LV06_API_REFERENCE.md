# Lucky Miner LV06 API Reference

This document provides the technical specifications for the LV06 (AxeOS) Stratum and HTTP APIs.

## 1. Stratum Protocol (TCP/3333)
The miner acts as a Stratum client. The following methods are supported:

### `mining.subscribe`
Initializes the connection.
*   **Request:** `{"id": 1, "method": "mining.subscribe", "params": ["AgentName"]}`
*   **Response:** `{"id": 1, "result": [ [ ["mining.set_difficulty", "sub_id_1"], ["mining.notify", "sub_id_2"] ], "extranonce1", extranonce2_size], "error": null}`

### `mining.authorize`
Authorizes the worker.
*   **Request:** `{"id": 2, "method": "mining.authorize", "params": ["worker_name", "password"]}`
*   **Response:** `{"id": 2, "result": true, "error": null}`

### `mining.notify` (Server to Client)
Sends a new work package.
*   **Params:** `[job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, ntime, clean_jobs]`
*   **Injection Point:** Data should be embedded in `coinb1`. Format: `[BitcoinHeader_12b] + [u_hex_Data_16b]`.

### `mining.submit` (Client to Server)
Sent when the miner finds a share.
*   **Params:** `[worker_name, job_id, extranonce2, ntime, nonce]`
*   **State Extraction:** Nonce is a 4-byte hex value at index 4 of the params array.

## 2. HTTP Config API (Port 80)
The miner exposes an HTTP server for system management.

### `PATCH /api/system`
Updates device parameters.
*   **Payload:** `{"frequency": 550}` (Frequency in MHz)
*   **Response:** `200 OK`

### `POST /api/reboot`
Triggers a soft reboot of the ESP32 and ASIC.
*   **Response:** `200 OK`

### `GET /api/status`
Retrieves telemetry.
*   **Includes:** `temp`, `hashrate`, `voltage`, `power`, `uptime`.

## 3. Coinbase Scripting
For high-fidelity data injection, use the following hex format in the `coinb1` field:
`[OPCode_PUSH_4][4_Bytes_uValue][OPCode_PUSH_10][10_Bytes_Padding]`
Totaling 16 bytes for the script section of the coinbase.
