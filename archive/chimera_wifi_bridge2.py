import socket
import json
import threading
import time

# CONFIGURACIÓN
HOST_IP = "0.0.0.0" 
PORT = 3333

class ChimeraStratumServerV2:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((HOST_IP, PORT))
        self.sock.listen(5)
        self.current_seed = "a" * 64 # Semilla de ejemplo
        print(f"\n🔥🔥 CHIMERA BRIDGE V2 (MODO DEPURACIÓN) 🔥🔥")
        print(f"Escuchando en puerto {PORT}...")
        print("Esperando a que el Sistema Límbico (ASIC) se conecte...\n")

    def handle_client(self, conn, addr):
        print(f"⚡ [NUEVA CONEXIÓN] Desde: {addr}")
        
        # Buffer para acumular datos fragmentados
        buffer = ""
        
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                
                # Decodificar y acumular
                text_chunk = data.decode('utf-8', errors='ignore')
                buffer += text_chunk
                
                # Procesar mensajes completos (separados por nueva línea)
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    message = message.strip()
                    
                    if not message:
                        continue # Ignorar líneas vacías
                    
                    print(f"📩 RECIBIDO de {addr[0]}: {message}") # VER QUÉ LLEGA
                    
                    try:
                        json_msg = json.loads(message)
                        self.process_message(json_msg, conn)
                    except json.JSONDecodeError:
                        print(f"⚠️ DATO NO JSON IGNORADO: {message}")

            except ConnectionResetError:
                break
            except Exception as e:
                print(f"❌ Error en el bucle: {e}")
                break
        
        print(f"🔌 [DESCONECTADO] {addr}")
        conn.close()

    def process_message(self, msg, conn):
        msg_id = msg.get('id')
        method = msg.get('method')
        
        # RESPUESTAS ESTÁNDAR
        if method == 'mining.subscribe':
            print(">> El Minero quiere suscribirse.")
            # Respuesta: [SessionID, ExtraNonce1, ExtraNonce2_Size]
            response = {"id": msg_id, "result": [[["mining.set_difficulty", "1"], ["mining.notify", "1"]], "08000002", 4], "error": None}
            self.send_json(conn, response)
            
        elif method == 'mining.authorize':
            print(">> El Minero envía credenciales (Autorizando...)")
            response = {"id": msg_id, "result": True, "error": None}
            self.send_json(conn, response)
            
            # ENVIAR EL PRIMER TRABAJO AL INSTANTE
            print(">> 💉 INYECTANDO PRIMERA SEMILLA...")
            self.set_difficulty(conn, 1024) # Dificultad baja para probar
            self.send_job(conn)

        elif method == 'mining.submit':
            print(f"🦋 >>> ¡¡INSIGHT (SHARE) RECIBIDO!! Nonce: {msg['params'][4]}")
            response = {"id": msg_id, "result": True, "error": None}
            self.send_json(conn, response)

    def send_json(self, conn, data):
        try:
            line = json.dumps(data) + '\n'
            conn.sendall(line.encode())
        except:
            pass

    def set_difficulty(self, conn, diff):
        msg = {"id": None, "method": "mining.set_difficulty", "params": [diff]}
        self.send_json(conn, msg)

    def send_job(self, conn):
        job_id = "job_1"
        coinbase = self.current_seed 
        # Merkle Root falso pero válido estructuralmente
        msg = {
            "params": [
                job_id,
                "0" * 64, # PrevHash
                coinbase, # Coinb1
                "0" * 64, # Coinb2
                [],       # Merkle Branch
                "20000000", # Version
                "1d00ffff", # nBits
                hex(int(time.time()))[2:], # nTime
                True
            ],
            "id": None,
            "method": "mining.notify"
        }
        self.send_json(conn, msg)

    def start(self):
        while True:
            try:
                conn, addr = self.sock.accept()
                thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                thread.start()
            except Exception as e:
                print(f"Error servidor: {e}")

if __name__ == "__main__":
    server = ChimeraStratumServerV2()
    server.start()