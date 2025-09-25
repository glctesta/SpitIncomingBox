import socket
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import pyodbc
import json
import win32print
import tempfile
import os
from datetime import datetime
from db_connection import DatabaseConnection
from config_manager import ConfigManager
import time
import threading
from queue import Queue
from PrinterConnection import PrinterConnection

class LoginWindow:
    def __init__(self, parent, on_login_success):
        self.window = tk.Toplevel(parent)
        self.window.title("Login")
        self.window.geometry("400x300")
        self.window.minsize(400, 300)
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        self._center_window()
        self.config_manager = ConfigManager()
        self.db_connection = None
        self.on_login_success = on_login_success
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.setup_ui()
        self.window.bind('<Return>', lambda e: self.login())
        self.username_entry.focus_set()

    def _center_window(self):
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')

    def setup_ui(self):
        main_frame = ttk.Frame(self.window, padding="30")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        title_label = ttk.Label(main_frame, text="Login", font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        ttk.Label(main_frame, text="Nome Utente:", font=('Arial', 10)).grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        self.username_entry = ttk.Entry(main_frame, textvariable=self.username_var, width=35)
        self.username_entry.grid(row=2, column=0, pady=(0, 20))
        self.username_entry.bind('<Return>', lambda e: self.password_entry.focus())

        ttk.Label(main_frame, text="Password:", font=('Arial', 10)).grid(row=3, column=0, sticky=tk.W, pady=(0, 5))
        self.password_entry = ttk.Entry(main_frame, textvariable=self.password_var, show="*", width=35)
        self.password_entry.grid(row=4, column=0, pady=(0, 30))
        self.password_entry.bind('<Return>', lambda e: self.login())

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, sticky=(tk.E, tk.W))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        self.login_button = ttk.Button(button_frame, text="Login", command=self.login, width=15)
        self.login_button.grid(row=0, column=0, padx=10)
        ttk.Button(button_frame, text="Annulla", command=self.window.destroy, width=15).grid(row=0, column=1, padx=10)

        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

    def login(self, event=None):
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            messagebox.showwarning("Attenzione", "Inserire nome utente e password")
            return

        if not self._connect_db():
            return

        try:
            user_info = self.db_connection.verify_credentials(username, password)
            if user_info:
                user_details = self._get_user_details(username)
                self.on_login_success(user_details)
                self.window.destroy()
            else:
                messagebox.showerror("Errore", "Nome utente o password non validi")
                self.password_var.set("")
                self.password_entry.focus()
        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante il login: {str(e)}")
        finally:
            if self.db_connection:
                self.db_connection.disconnect()

    def _get_user_details(self, username):
        try:
            cursor = self.db_connection.connection.cursor()
            cursor.execute("""
                SELECT UserId, Name, [Name] as Username 
                FROM dbo.[User] 
                WHERE [name] = ?
            """, username)

            result = cursor.fetchone()
            if result:
                class User:
                    def __init__(self, user_id, name, username):
                        self.UserId = user_id
                        self.Name = name
                        self.Username = username
                return User(result[0], result[1], result[2])
            return None
        except Exception as e:
            print(f"Errore nel recupero dettagli utente: {e}")
            return None

    def _connect_db(self):
        try:
            self.db_connection = DatabaseConnection(self.config_manager)
            self.db_connection.connect()
            return True
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile connettersi al database: {str(e)}")
            return False

class BoxSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Box Splitter Application")
        self.root.geometry("800x600")
        self.is_logged_in = False

        self.main_frame = ttk.Frame(self.root)
        self.main_frame.grid(row=0, column=0, sticky='nsew')

        self.config_manager = ConfigManager()
        self.db_connection = DatabaseConnection(self.config_manager)
        self.current_user = None
        self.current_user_id = None
        self.current_data = None
        self.printer_config = {}
        self.printer_config_file = "printer_config.json"

        self.status_var = tk.StringVar(value="Pronto")
        self.batch_number_var = tk.StringVar()
        self.divisions_var = tk.IntVar(value=2)

        self.load_printer_config()
        self.setup_ui()
        self.show_login()

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # CORREZIONE: Inizializzazione corretta della stampante
        self.printer = None
        self._initialize_printer()

    def _initialize_printer(self):
        """Inizializza la connessione con la stampante - VERSIONE CORRETTA"""
        try:
            if not hasattr(self, 'printer_config'):
                self.load_printer_config()

            # CORREZIONE: Crea l'istanza correttamente
            self.printer = PrinterConnection(  # Solo questo, niente parentesi extra
                ip_address=self.printer_config.get('ip_address'),
                port=int(self.printer_config.get('port', 9100)),
                timeout=5
            )

            print(f"Stampante configurata: {self.printer_config.get('ip_address')}:{self.printer_config.get('port')}")
            return True

        except Exception as e:
            print(f"Errore nell'inizializzazione della stampante: {str(e)}")
            self.printer = None
            return False

    def _print_split_label_safe(self, item_code, quantity, batch_number):
        """Metodo specifico per la stampa delle etichette split"""
        return self._print_label_safe(item_code, quantity, batch_number)

    def setup_ui(self):
        # Frame principale
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self._setup_logo_frame(main_frame)
        self._setup_user_frame(main_frame)
        self._setup_search_frame(main_frame)
        self._setup_info_frame(main_frame)
        self._setup_split_frame(main_frame)
        self._setup_printer_frame(main_frame)
        self._setup_status_bar(main_frame)

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

    def _setup_logo_frame(self, parent):
        """Setup del frame per il logo"""
        self.logo_frame = ttk.Frame(parent)
        self.logo_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 20))

        try:
            from PIL import Image, ImageTk
            import os

            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Logo.png")
            print(f"Tentativo di caricare il logo da: {logo_path}")

            if os.path.exists(logo_path):
                logo_image = Image.open(logo_path)
                print(f"Dimensioni originali logo: {logo_image.size}")

                # Ridimensionamento
                basewidth = 200
                wpercent = (basewidth / float(logo_image.size[0]))
                hsize = int((float(logo_image.size[1]) * float(wpercent)))
                logo_image = logo_image.resize((basewidth, hsize), Image.Resampling.LANCZOS)
                print(f"Dimensioni logo dopo resize: {logo_image.size}")

                self.logo_photo = ImageTk.PhotoImage(logo_image)
                self.logo_label = ttk.Label(self.logo_frame, image=self.logo_photo)
                self.logo_label.grid(row=0, column=0)
                print("Label del logo creata e posizionata")
            else:
                raise FileNotFoundError(f"File logo non trovato: {logo_path}")

        except Exception as e:
            print(f"Errore nel caricamento del logo: {str(e)}")
            self.logo_label = ttk.Label(self.logo_frame, text="Logo non disponibile")
            self.logo_label.grid(row=0, column=0)

    def _setup_user_frame(self, parent):
        user_frame = ttk.Frame(parent)
        user_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        self.user_label = ttk.Label(user_frame, text="Utente: Non loggato")
        self.user_label.pack(side=tk.LEFT, padx=5)

        ttk.Button(user_frame, text="Login", command=self.show_login).pack(side=tk.RIGHT, padx=5)
        ttk.Button(user_frame, text="Logout", command=self.logout).pack(side=tk.RIGHT, padx=5)

    def _setup_search_frame(self, parent):
        search_frame = ttk.LabelFrame(parent, text="Cerca Scatola", padding="5")
        search_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(search_frame, text="Batch Number HU:").grid(row=0, column=0, sticky=tk.W)
        batch_entry = ttk.Entry(search_frame, textvariable=self.batch_number_var, width=30)
        batch_entry.grid(row=0, column=1, padx=5)
        batch_entry.bind('<Return>', lambda e: self.search_batch())

        ttk.Button(search_frame, text="Cerca", command=self.search_batch).grid(row=0, column=2, padx=5)

    def _setup_info_frame(self, parent):
        info_frame = ttk.LabelFrame(parent, text="Informazioni Scatola", padding="5")
        info_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        self.info_text = tk.Text(info_frame, height=8, width=70)
        self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.info_text.config(yscrollcommand=scrollbar.set)

        info_frame.grid_rowconfigure(0, weight=1)
        info_frame.grid_columnconfigure(0, weight=1)

    # def _setup_split_frame(self, parent):
    #     split_frame = ttk.LabelFrame(parent, text="Split Quantità", padding="5")
    #     split_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
    #
    #     ttk.Label(split_frame, text="Numero di divisioni:").grid(row=0, column=0, sticky=tk.W)
    #     divisions_spinbox = ttk.Spinbox(split_frame, from_=2, to=10, textvariable=self.divisions_var, width=5)
    #     divisions_spinbox.grid(row=0, column=1, padx=5)
    #     divisions_spinbox.bind('<Return>', lambda e: self.input_quantities())
    #
    #     ttk.Button(split_frame, text="Inserisci Quantità", command=self.input_quantities).grid(row=0, column=2, padx=5)

    #Funzione aggiunta per aumentare il numero degli split
    def _setup_split_frame(self, parent):
        """Setup del frame per lo split delle quantità"""
        split_frame = ttk.LabelFrame(parent, text="Split Quantità", padding="5")
        split_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(split_frame, text="Numero di divisioni:").grid(row=0, column=0, sticky=tk.W)

        # Modifica qui: aumentiamo il limite massimo e aggiungiamo validazione
        divisions_spinbox = ttk.Spinbox(
            split_frame,
            from_=2,
            to=100,  # Aumentiamo il limite massimo a 100
            textvariable=self.divisions_var,
            width=5,
            validate='all',
            validatecommand=(split_frame.register(self._validate_divisions), '%P')
        )
        divisions_spinbox.grid(row=0, column=1, padx=5)
        divisions_spinbox.bind('<Return>', lambda e: self.input_quantities())

        ttk.Button(split_frame, text="Inserisci Quantità", command=self.input_quantities).grid(row=0, column=2, padx=5)

    def _validate_divisions(self, value):
        """Valida l'input del numero di divisioni"""
        if value == "":
            return True
        try:
            num = int(value)
            return 2 <= num <= 100  # Permette valori tra 2 e 100
        except ValueError:
            return False

    def _setup_printer_frame(self, parent):
        printer_frame = ttk.LabelFrame(parent, text="Configurazione Stampante", padding="5")
        printer_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Button(printer_frame, text="Configura Stampante", command=self.configure_printer).grid(row=0, column=0,
                                                                                                   padx=5)
        self.printer_label = ttk.Label(printer_frame,
                                       text=f"Stampante: {self.printer_config.get('ip_address', 'Non configurata')}:{self.printer_config.get('port', 'N/A')}")
        self.printer_label.grid(row=0, column=1, padx=5)

    def _setup_status_bar(self, parent):
        status_bar = ttk.Label(parent, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

    def show_login(self):
        """Mostra la finestra di login"""
        LoginWindow(self.root, self.on_login_success)

    def on_login_success(self, user_info):
        """Callback eseguito quando il login ha successo"""
        if user_info:
            self.current_user = user_info.Name
            self.current_user_id = user_info.UserId
            self.user_label.config(text=f"Utente: {user_info.Name} (ID: {user_info.UserId})")
            self.status_var.set(f"Login effettuato come {user_info.Name}")
            self.is_logged_in = True
        else:
            messagebox.showerror("Errore", "Impossibile recuperare i dettagli dell'utente")

    def logout(self):
        """Gestisce il logout dell'utente"""
        if self.current_user:
            self.current_user = None
            self.current_user_id = None
            self.user_label.config(text="Utente: Non loggato")
            self.status_var.set("Logout effettuato")
            self.info_text.delete(1.0, tk.END)
            self.batch_number_var.set("")
            self.current_data = None
            self.is_logged_in = False
        else:
            messagebox.showinfo("Info", "Nessun utente loggato")

    def load_printer_config(self):
        """Carica la configurazione della stampante"""
        try:
            with open(self.printer_config_file, 'r') as f:
                self.printer_config = json.load(f)

            # Validazione dei parametri necessari
            required_params = ['ip_address', 'port', 'printer_name']
            missing_params = [param for param in required_params
                              if param not in self.printer_config]

            if missing_params:
                raise ValueError(f"Parametri mancanti nel file di configurazione: {missing_params}")

            # Validazione del tipo di dati
            if not isinstance(self.printer_config['port'], (int, str)):
                raise ValueError("Il parametro 'port' deve essere un numero")

        except FileNotFoundError:
            messagebox.showerror("Errore",
                                 f"File di configurazione stampante non trovato: {self.printer_config_file}")
            self.printer_config = {}
        except json.JSONDecodeError:
            messagebox.showerror("Errore",
                                 "File di configurazione stampante non valido")
            self.printer_config = {}
        except Exception as e:
            messagebox.showerror("Errore",
                                 f"Errore nel caricamento della configurazione stampante:\n{str(e)}")

    def _get_default_printer_config(self):
        """Restituisce la configurazione predefinita della stampante"""
        return {
            "ip_address": "localhost",
            "port": 9100
        }

    def save_printer_config(self):
        """Salva la configurazione della stampante su file"""
        try:
            with open(self.printer_config_file, 'w') as f:
                json.dump(self.printer_config, f, indent=4)
            self.printer_label.config(
                text=f"Stampante: {self.printer_config.get('ip_address', 'Non configurata')}:{self.printer_config.get('port', 'N/A')}")
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile salvare la configurazione: {str(e)}")

    def search_batch(self):
        """Cerca il batch number nel database"""
        if not self._validate_search_prerequisites():
            return

        batch_number = self.batch_number_var.get().strip()
        try:
            if not self._ensure_database_connection():
                return

            result = self._execute_batch_search(batch_number)
            if result:
                self._display_batch_info(result)
            else:
                self._handle_batch_not_found(batch_number)
        except Exception as e:
            self._handle_search_error(e)

    def _validate_search_prerequisites(self):
        """Valida i prerequisiti per la ricerca"""
        if not self.batch_number_var.get().strip():
            messagebox.showwarning("Attenzione", "Inserire un Batch Number")
            return False
        if not self.is_logged_in:
            messagebox.showwarning("Attenzione", "Effettuare prima il login")
            return False
        return True

    def _ensure_database_connection(self):
        """Assicura che la connessione al database sia attiva"""
        try:
            if not self.db_connection or not self.db_connection.is_connected():
                self.db_connection.connect()
            return True
        except Exception as e:
            messagebox.showerror("Errore Database", f"Impossibile connettersi al database: {str(e)}")
            return False

    def _execute_batch_search(self, batch_number):
        """Esegue la query di ricerca del batch"""
        cursor = self.db_connection.connection.cursor()
        cursor.execute("""
            SELECT 
                i.incomingid, 
                id.incomingdetid, 
                i.number, 
                it.itemid, 
                it.Code, 
                p.BatchNumber_HU, 
                p.Qty AS PackQty, 
                id.Qty AS IncomingQty, 
                l.locationid, 
                l.Code AS LocationCode,
                p.PackingId
            FROM dbo.incoming i 
            INNER JOIN dbo.incomingdet id ON i.IncomingId = id.incomingid	
            INNER JOIN dbo.item it ON it.itemid = id.ItemId 
            INNER JOIN dbo.packing p ON id.IncomingDetId = p.IncomingDetId 
            INNER JOIN dbo.Location L ON p.LocationId = l.locationid
            WHERE p.BatchNumber_HU = ?
        """, batch_number)
        return cursor.fetchone()

    def _display_batch_info(self, result):
        """Visualizza le informazioni del batch trovato"""
        self.current_data = result
        info_text = f"""Codice Prodotto: {result.Code}
Numero Incoming: {result.number}
Quantità Iniziale: {result.IncomingQty}
Quantità Packing: {result.PackQty}
Locazione: {result.LocationCode}
Batch Number: {result.BatchNumber_HU}"""

        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, info_text)
        self.status_var.set("Batch trovato")

    def _handle_batch_not_found(self, batch_number):
        """Gestisce il caso in cui il batch non viene trovato"""
        messagebox.showinfo("Info", f"Batch number '{batch_number}' non trovato nel database")
        self.current_data = None
        self.info_text.delete(1.0, tk.END)
        self.status_var.set("Batch non trovato")

    def _handle_search_error(self, error):
        """Gestisce gli errori durante la ricerca"""
        messagebox.showerror("Errore", f"Errore durante la ricerca: {str(error)}")
        self.status_var.set("Errore durante la ricerca")

    def input_quantities(self):
        """Gestisce l'input delle quantità per lo split"""
        if not self.current_data:
            messagebox.showwarning("Attenzione", "Cercare prima un batch number")
            return

        divisions = self.divisions_var.get()
        if divisions < 2:
            messagebox.showwarning("Attenzione", "Il numero di divisioni deve essere almeno 2")
            return

        self._show_quantities_dialog(divisions)

    #Funzione aggiunta per validare oltre 11 scatole fino a 100
    def _show_quantities_dialog(self, divisions):
        """Mostra la finestra di dialogo per l'inserimento delle quantità"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Inserisci Quantità")
        dialog.geometry("400x600")  # Aumentiamo l'altezza della finestra
        dialog.transient(self.root)
        dialog.grab_set()

        # Frame principale con scrollbar
        container = ttk.Frame(dialog)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Canvas e scrollbar
        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Configurazione grid
        container.grid_columnconfigure(0, weight=1)

        # Visualizzazione quantità totale
        total_qty = float(self.current_data.PackQty)
        ttk.Label(scrollable_frame, text=f"Quantità totale: {total_qty}",
                  font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)

        # Lista per tenere traccia delle entry
        entries = []

        # Creazione delle entry per le quantità
        for i in range(divisions):
            ttk.Label(scrollable_frame, text=f"Quantità {i + 1}:").grid(
                row=i + 1, column=0, sticky=tk.W, pady=5)
            entry_var = tk.StringVar()
            entry = ttk.Entry(scrollable_frame, textvariable=entry_var, width=15)
            entry.grid(row=i + 1, column=1, padx=5, pady=5)
            entries.append(entry_var)

            if i < divisions - 1:
                entry.bind('<Return>',
                           lambda e, next_idx=i + 1: scrollable_frame.grid_slaves(
                               row=next_idx + 1, column=1)[0].focus())

        # Frame per i pulsanti
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.grid(row=divisions + 1, column=0, columnspan=2, pady=20)

        def validate_and_split():
            try:
                quantities = []
                for i, entry_var in enumerate(entries):
                    value = entry_var.get().strip()
                    if not value:
                        raise ValueError(f"Inserire la quantità {i + 1}")
                    quantities.append(float(value))

                if abs(sum(quantities) - total_qty) > 0.01:
                    raise ValueError(
                        f"La somma delle quantità ({sum(quantities)}) non corrisponde al totale ({total_qty})")

                dialog.destroy()
                self.perform_split(quantities)
            except ValueError as e:
                messagebox.showerror("Errore", str(e))

        ttk.Button(button_frame, text="Conferma",
                   command=validate_and_split).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Annulla",
                   command=dialog.destroy).pack(side=tk.LEFT, padx=10)

        # Configurazione scrollbar
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Focus sul primo campo
        if entries:
            scrollable_frame.grid_slaves(row=1, column=1)[0].focus()

    def split_box(self):
        """Gestisce l'intero processo di split della scatola"""
        try:
            # Validazione input
            if not self._validate_split_input():
                return

            # Ottieni le quantità
            quantities = self._calculate_quantities()
            if not quantities:
                return

            # Conferma dall'utente
            if not self._confirm_split(quantities):
                return

            # Salva nel database
            if not self._save_split_to_database(quantities):
                return

            # Stampa le etichette
            if not self._print_labels(quantities):
                # Se la stampa fallisce, fai rollback del database
                self._rollback_split()
                return

            # Aggiorna l'interfaccia
            self._reset_after_split()

            messagebox.showinfo("Successo", "Operazione completata con successo!")

        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante lo split: {str(e)}")
            self._rollback_split()

    def perform_split(self, quantities):
        """Esegue lo split delle quantità"""
        if not self.current_data:
            messagebox.showerror("Errore", "Nessun dato disponibile per lo split")
            return

        if not self._ensure_database_connection():
            return

        # Prepara tutte le etichette da stampare
        labels_to_print = []
        labels_to_print.append({
            'item_code': self.current_data.Code,
            'quantity': str(quantities[0]),
            'batch_number': self.current_data.BatchNumber_HU
        })

        for i, qty in enumerate(quantities[1:], 1):
            new_batch_number = f"{self.current_data.BatchNumber_HU}_{i}"
            labels_to_print.append({
                'item_code': self.current_data.Code,
                'quantity': str(qty),
                'batch_number': new_batch_number
            })

        print("Inizio processo di stampa etichette...")
        current_label_index = 0

        while current_label_index < len(labels_to_print):
            label = labels_to_print[current_label_index]
            print(f"Tentativo di stampa etichetta {current_label_index + 1} di {len(labels_to_print)}")

            try:
                success = self._print_label_safe(
                    item_code=label['item_code'],
                    quantity=label['quantity'],
                    batch_number=label['batch_number']
                )

                if success:
                    print(f"Etichetta {current_label_index + 1} stampata con successo")
                    current_label_index += 1
                else:
                    raise Exception("Errore durante la stampa dell'etichetta")

            except Exception as e:
                error_message = f"Errore durante la stampa dell'etichetta {current_label_index + 1}:\n{str(e)}\nVuoi riprovare?"
                response = messagebox.askretrycancel("Errore Stampa", error_message)

                if not response:
                    messagebox.showerror("Operazione Annullata", "Split annullato. Nessuna modifica salvata.")
                    return

        # Se tutte le etichette sono stampate, salva nel database
        self._save_split_to_database(quantities)

    def _rollback_split(self):
        """Esegue il rollback delle modifiche in caso di errore"""
        try:
            if self.db_connection.connection:
                self.db_connection.connection.rollback()
                print("Eseguito rollback delle modifiche al database")
        except Exception as e:
            print(f"Errore durante il rollback: {str(e)}")

    def _save_split_to_database(self, quantities):
        """Salva le modifiche dello split nel database"""
        try:
            with self.db_connection.connection as connection:
                cursor = connection.cursor()
                original_was = f"1 x {self.current_data.PackQty}"

                cursor.execute("""
                    UPDATE dbo.incomingdet
                    SET Qty = ?, OriginalWas = ?
                    WHERE incomingdetid = ?
                """, quantities[0], original_was, self.current_data.incomingdetid)

                cursor.execute("""
                    UPDATE dbo.Packing
                    SET qty = ?, BatchNumber_HU = ?
                    WHERE packingid = ?
                """, quantities[0], self.current_data.BatchNumber_HU, self.current_data.PackingId)

                for i, qty in enumerate(quantities[1:], 1):
                    new_batch_number = f"{self.current_data.BatchNumber_HU}-{i}"

                    cursor.execute("""
                        INSERT INTO dbo.incomingdet
                        (incomingid, itemid, batchnumber, Qty, OriginalWas)
                        OUTPUT INSERTED.IncomingDetId
                        VALUES (?, ?, ?, ?, ?)
                    """, self.current_data.incomingid, self.current_data.itemid,
                                   new_batch_number, qty, original_was)

                    new_incomingdet_id = cursor.fetchone()[0]

                    cursor.execute("""
                        INSERT INTO dbo.packing
                        (IncomingDetId, LocationId, Qty, Code, BatchNumber_HU,[CurrentDate],UserId)
                        VALUES (?, ?, ?, ?, ?,GetDate(),?)
                    """, new_incomingdet_id, self.current_data.locationid,
                                   qty, new_batch_number, new_batch_number, self.current_user_id)

                    cursor.execute("""
                        INSERT INTO dbo.SplitBoxes
                        (UserId, IncomingDetid)
                        VALUES (?, ?)
                    """, self.current_user_id, new_incomingdet_id)

                connection.commit()
                messagebox.showinfo("Successo", "Split e stampa completati con successo!")
                self._reset_after_split()

        except Exception as e:
            if self.db_connection.connection:
                self.db_connection.connection.rollback()
            messagebox.showerror("Errore", f"Errore durante il salvataggio: {str(e)}")

    def _confirm_split(self, quantities):
        """Chiede conferma all'utente per lo split"""
        message = "Confermi di voler dividere la scatola nelle seguenti quantità?\n\n"
        message += f"Scatola originale: {quantities[0]} pezzi\n"
        for i, qty in enumerate(quantities[1:], 1):
            message += f"Nuova scatola {i}: {qty} pezzi\n"

        return messagebox.askyesno("Conferma Split", message)

    def _validate_split_input(self):
        """Valida i dati di input prima dello split"""
        try:
            # Verifica che ci siano dati correnti
            if not hasattr(self, 'current_data') or not self.current_data:
                raise ValueError("Nessun dato selezionato per lo split")

            # Verifica che l'utente sia loggato
            if not hasattr(self, 'current_user_id') or not self.current_user_id:
                raise ValueError("Utente non autenticato")

            # Verifica connessione database
            if not self.db_connection or not self.db_connection.connection:
                raise ValueError("Connessione al database non disponibile")

            # Verifica che la quantità totale sia corretta
            total_qty = sum(self._calculate_quantities())
            if total_qty != self.current_data.PackQty:
                raise ValueError(
                    f"La quantità totale ({total_qty}) non corrisponde alla quantità originale ({self.current_data.PackQty})")

            return True

        except Exception as e:
            messagebox.showerror("Errore Validazione", str(e))
            return False

    def _ensure_printer_connection(self):
        """Verifica e ristabilisce la connessione con la stampante"""
        try:
            if self.printer is None:
                if not self._initialize_printer():
                    return False

            if not self.printer.is_connected():
                print("Tentativo di connessione alla stampante...")
                return self.printer.connect()

            return True
        except Exception as e:
            print(f"Errore di connessione alla stampante: {str(e)}")
            return False

    def _print_label_safe(self, item_code, quantity, batch_number):
        """Stampa l'etichetta con gestione degli errori"""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                print(f"Tentativo di stampa {retry_count + 1} per {batch_number}")

                if not self._ensure_printer_connection():
                    print("Connessione stampante non disponibile")
                    retry_count += 1
                    time.sleep(2)
                    continue

                success = self.printer.print_label(
                    item_code=item_code,
                    quantity=quantity,
                    batch_number=batch_number
                )

                if success:
                    print(f"Etichetta stampata con successo: {batch_number}")
                    return True
                else:
                    print(f"Stampa fallita per {batch_number}")
                    retry_count += 1
                    time.sleep(2)

            except Exception as e:
                print(f"Errore durante la stampa (tentativo {retry_count + 1}): {str(e)}")
                retry_count += 1
                time.sleep(2)

        print(f"Tutti i {max_retries} tentativi di stampa falliti per {batch_number}")
        return False

    def print_label(self, item_code, quantity, batch_number):
        """Metodo per la stampa delle etichette con retry"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.printer is None:
                    if not self._initialize_printer():
                        raise Exception("Impossibile inizializzare la stampante")

                success = self.printer.print_label(item_code, quantity, batch_number)
                if success:
                    return True

            except Exception as e:
                if attempt == max_retries - 1:  # Ultimo tentativo
                    messagebox.showerror("Errore Stampa",
                                         f"Impossibile stampare l'etichetta dopo {max_retries} tentativi:\n{str(e)}")
                    return False
                time.sleep(1)  # Attendi prima del retry
                continue
        return False

    def verify_printer_config(self):
        """Verifica che la configurazione della stampante sia valida"""
        if not self.printer_config:
            return False

        required_fields = ['ip_address', 'port']
        for field in required_fields:
            if not self.printer_config.get(field):
                return False

        try:
            port = int(self.printer_config['port'])
            if port <= 0 or port > 65535:
                return False
        except ValueError:
            return False

        return True

    def _reset_after_split(self):
        """Resetta l'interfaccia dopo uno split completato"""
        self.batch_number_var.set("")
        self.info_text.delete(1.0, tk.END)
        self.current_data = None
        self.status_var.set("Split completato")

    def configure_printer(self):
        """Mostra la finestra di configurazione della stampante"""
        config_window = tk.Toplevel(self.root)
        config_window.title("Configura Stampante")
        config_window.geometry("400x200")
        config_window.transient(self.root)
        config_window.grab_set()

        # Campi di configurazione
        ip_var = tk.StringVar(value=self.printer_config.get('ip_address', ''))
        port_var = tk.StringVar(value=str(self.printer_config.get('port', '9100')))

        # Layout
        ttk.Label(config_window, text="IP Address:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(config_window, textvariable=ip_var, width=20).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(config_window, text="Porta:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(config_window, textvariable=port_var, width=10).grid(row=1, column=1, padx=5, pady=5)

        def test_connection():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5)
                    s.connect((ip_var.get(), int(port_var.get())))
                    messagebox.showinfo("Successo", "Connessione alla stampante riuscita!")
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile connettersi alla stampante: {str(e)}")

        def save_config():
            try:
                # Verifica che la porta sia un numero valido
                port = int(port_var.get())
                if port <= 0 or port > 65535:
                    raise ValueError("Porta non valida")

                self.printer_config.update({
                    'ip_address': ip_var.get().strip(),
                    'port': port
                })
                self.save_printer_config()
                messagebox.showinfo("Successo", "Configurazione stampante salvata")
                config_window.destroy()
            except ValueError as e:
                messagebox.showerror("Errore", "La porta deve essere un numero valido tra 1 e 65535")

        ttk.Button(config_window, text="Test Connessione", command=test_connection).grid(row=2, column=0, columnspan=2,
                                                                                         pady=10)
        ttk.Button(config_window, text="Salva", command=save_config).grid(row=3, column=0, pady=5)
        ttk.Button(config_window, text="Annulla", command=config_window.destroy).grid(row=3, column=1, pady=5)


def main():
    try:
        root = tk.Tk()
        app = BoxSplitterApp(root)
        root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root))
        root.mainloop()
    except KeyboardInterrupt:
        print("\nApplicazione terminata dall'utente")
    except Exception as e:
        print(f"Errore imprevisto: {e}")
    finally:
        try:
            root.destroy()
        except:
            pass

def on_closing(root):
    """Gestisce la chiusura pulita dell'applicazione"""
    try:
        if messagebox.askokcancel("Chiudi", "Vuoi chiudere l'applicazione?"):
            root.quit()
            root.destroy()
    except:
        root.destroy()

if __name__ == "__main__":
    main()