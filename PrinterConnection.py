import socket
import time

class PrinterConnection:
    def __init__(self, ip_address=None, port=9100, timeout=5):
        self.ip_address = ip_address
        self.port = port
        self.timeout = timeout
        self._socket = None
        self.connected = False
        self.last_print_time = 0
        self.reconnect_delay = 2

    def connect(self):
        """Stabilisce la connessione con la stampante"""
        try:
            if self._socket:
                self.disconnect()

            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.ip_address, self.port))
            self.connected = True
            print(f"Connessione stabilita con {self.ip_address}:{self.port}")
            return True
        except Exception as e:
            print(f"Errore di connessione: {str(e)}")
            self.connected = False
            self._socket = None
            return False

    def disconnect(self):
        """Chiude la connessione con la stampante"""
        try:
            if self._socket:
                self._socket.close()
        except:
            pass
        finally:
            self._socket = None
            self.connected = False

    def print_label(self, item_code, quantity, batch_number):
        """Stampa un'etichetta con i dati forniti"""
        try:
            if not self.connected:
                if not self.connect():
                    return False

            zpl_command = f"""
^XA
^FO50,50^A0N,45,45^FDProdotto: {item_code}^FS
^FO50,120^A0N,35,35^FDCodice: {item_code}^FS
^FO50,180^BY3,2,80
^BCN,80,Y,N,N,A^FD{item_code}^FS
^FO50,300^A0N,35,35^FDQuantità: {quantity}^FS
^FO50,350^BY3,2,80
^BCN,80,Y,N,N,A^FD{quantity}^FS
^FO50,470^A0N,35,35^FDLotto: {batch_number}^FS
^FO50,520^BY3,2,80
^BCN,80,Y,N,N,A^FD{batch_number}^FS
^XZ
"""
            self._socket.send(zpl_command.encode())
            time.sleep(0.5)
            self.last_print_time = time.time()
            print(f"Stampa completata: {batch_number}")
            return True

        except Exception as e:
            print(f"Errore durante la stampa: {str(e)}")
            self.disconnect()
            return False

    def is_connected(self):
        """Verifica se la stampante è connessa"""
        if not self._socket or not self.connected:
            return False
        try:
            self._socket.settimeout(1)
            self._socket.send(b'\x00')
            return True
        except:
            self.connected = False
            return False