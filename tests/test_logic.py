from database import DatabaseClient
from logic.ipc import IPCLogic
from logic.empleo import EmpleoLogic
import os
from dotenv import load_dotenv
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)

load_dotenv()

print("Initializing DatabaseClient...")
db = DatabaseClient(
    os.getenv('HOST_DBB'), 
    int(os.getenv('DB_PORT', 3306)), 
    os.getenv('USER_DBB'), 
    os.getenv('PASSWORD_DBB'), 
    {
        'datalake_economico': os.getenv('NAME_DBB_DATALAKE_ECONOMICO'),
        'dwh_socio': os.getenv('NAME_DBB_DWH_SOCIO')
    }
)

print("\n--- Testing IPC Logic ---")
try:
    ipc = IPCLogic(db)
    result = ipc.get_latest_ipc()
    print("IPC Result:")
    print(result)
except Exception as e:
    print(f"IPC Error: {e}")

print("\n--- Testing Employment Logic ---")
try:
    empleo = EmpleoLogic(db)
    result = empleo.get_latest_employment_data()
    print("Employment Result:")
    print(result)
except Exception as e:
    print(f"Employment Error: {e}")
