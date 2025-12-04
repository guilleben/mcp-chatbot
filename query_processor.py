"""Procesador de queries especiales del menú.

Convierte queries especiales como "datalake_economico_ultimo_valor" en consultas reales a la base de datos.
"""
import logging
import re
from typing import Optional, Dict, Any, List
from database import DatabaseClient


class QueryProcessor:
    """Procesa queries especiales del menú y las convierte en consultas reales."""
    
    def __init__(self, db_client: DatabaseClient):
        """Inicializar procesador de queries.
        
        Args:
            db_client: Cliente de base de datos
        """
        self.db_client = db_client
    
    def process_special_query(self, db_query: str, user_input: Optional[str] = None) -> Optional[str]:
        """Procesar un query especial del menú.
        
        Args:
            db_query: Query especial del menú (ej: "datalake_economico_ultimo_valor")
            user_input: Input del usuario (opcional, para consultas personalizadas)
            
        Returns:
            Query procesado para buscar en la base de datos, o None si no se puede procesar
        """
        if not db_query:
            return None
        
        # Detectar tipo de query especial
        query_lower = db_query.lower()
        
        # Extraer base de datos del query
        db_match = re.match(r'^(datalake_|dwh_)?(economico|socio|sociodemografico)', query_lower)
        if not db_match:
            # Si no se puede extraer, usar el query tal cual
            return db_query
        
        db_prefix = db_match.group(1) or ""
        db_type = db_match.group(2)
        
        # Determinar nombre completo de la base de datos (usar claves de la configuración)
        if db_prefix.startswith("datalake_"):
            if db_type == "economico":
                db_name = "datalake_economico"
            else:
                db_name = "datalake_socio"  # Usar la clave correcta de la configuración
        elif db_prefix.startswith("dwh_"):
            if db_type == "economico":
                db_name = "dwh_economico"
            else:
                db_name = "dwh_socio"  # Usar la clave correcta de la configuración
        else:
            # Sin prefijo, determinar por tipo
            if db_type == "economico":
                db_name = "datalake_economico"  # Por defecto datalake
            else:
                db_name = "datalake_socio"  # Usar la clave correcta de la configuración
        
        # Procesar según el tipo de query especial
        if "ultimo_valor" in query_lower or "último valor" in query_lower:
            return self._process_ultimo_valor(db_name)
        elif "ver_grafico" in query_lower or "ver gráfico" in query_lower or "ver grafico" in query_lower:
            # Para ver gráfico, también necesitamos datos, así que obtener últimos valores
            return self._process_ultimo_valor(db_name)
        elif "comparar_fechas" in query_lower or "comparar fechas" in query_lower:
            # Para comparar fechas, también obtener últimos valores para comparar
            return self._process_ultimo_valor(db_name)
        elif "consulta_personalizada" in query_lower or "consulta personalizada" in query_lower:
            # Para consultas personalizadas, usar el input del usuario si está disponible
            if user_input and user_input.strip() and user_input != db_query:
                return user_input
            # Si no hay input, buscar información general de la base de datos
            return self._process_ultimo_valor(db_name)
        else:
            # Query no reconocido, intentar buscar directamente
            return db_query
    
    def _process_ultimo_valor(self, db_name: str) -> str:
        """Procesar query de último valor.
        
        Args:
            db_name: Nombre de la base de datos
            
        Returns:
            Query para buscar el último valor
        """
        # Buscar el último valor disponible en la base de datos
        return f"último valor {db_name}"
    
    def get_latest_data(self, db_key: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtener los datos más recientes de una base de datos.
        
        Args:
            db_key: Clave de la base de datos (ej: "datalake_economico")
            limit: Número máximo de resultados
            
        Returns:
            Lista de registros más recientes
        """
        if not self.db_client:
            logging.warning("No database client available")
            return []
        
        results = []
        try:
            # Obtener el nombre real de la base de datos desde la configuración
            db_name = self.db_client.databases.get(db_key)
            if not db_name:
                logging.warning(f"Database key '{db_key}' not found in configuration. Available keys: {list(self.db_client.databases.keys())}")
                return []
            
            logging.info(f"Getting latest data from database: {db_name} (key: {db_key})")
            
            # Obtener estructura de la base de datos
            structure = self.db_client.get_database_structure()
            
            if db_name not in structure:
                logging.warning(f"Database '{db_name}' not found in structure. Available databases: {list(structure.keys())}")
                return []
            
            tables = structure[db_name]
            
            if not tables:
                logging.warning(f"No tables found in database {db_name}")
                return []
            
            logging.info(f"Found {len(tables)} tables in database {db_name}")
            
            # Buscar en más tablas para obtener datos (aumentar de 5 a 10 para más datos)
            for table_name, table_info in list(tables.items())[:10]:
                try:
                    # Buscar columna de fecha
                    columns = table_info.get('columns', [])
                    date_columns = [c for c in columns if 'fecha' in c.lower() or 'date' in c.lower() or 'año' in c.lower() or 'ano' in c.lower()]
                    
                    if date_columns:
                        # Obtener últimos registros ordenados por fecha
                        try:
                            with self.db_client.connect(db_name) as conn:
                                from sqlalchemy import text
                                order_by_col = date_columns[0]
                                query = text(f"SELECT * FROM `{table_name}` ORDER BY `{order_by_col}` DESC LIMIT :limit")
                                result = conn.execute(query, {'limit': limit})
                                
                                for row in result.fetchall():
                                    row_dict = dict(row._mapping)
                                    row_dict['_source_db'] = db_name
                                    row_dict['_source_table'] = table_name
                                    results.append(row_dict)
                                    
                                    if len(results) >= limit:
                                        break
                        except Exception as e:
                            logging.debug(f"Error querying table {table_name} with date column: {e}")
                            # Si falla con fecha, intentar sin ordenar
                            try:
                                with self.db_client.connect(db_name) as conn:
                                    from sqlalchemy import text
                                    query = text(f"SELECT * FROM `{table_name}` LIMIT :limit")
                                    result = conn.execute(query, {'limit': limit})
                                    
                                    for row in result.fetchall():
                                        row_dict = dict(row._mapping)
                                        row_dict['_source_db'] = db_name
                                        row_dict['_source_table'] = table_name
                                        results.append(row_dict)
                                        
                                        if len(results) >= limit:
                                            break
                            except Exception as e2:
                                logging.debug(f"Error querying table {table_name} without date: {e2}")
                                continue
                    else:
                        # Si no hay columna de fecha, obtener registros directamente
                        try:
                            with self.db_client.connect(db_name) as conn:
                                from sqlalchemy import text
                                query = text(f"SELECT * FROM `{table_name}` LIMIT :limit")
                                result = conn.execute(query, {'limit': limit})
                                
                                for row in result.fetchall():
                                    row_dict = dict(row._mapping)
                                    row_dict['_source_db'] = db_name
                                    row_dict['_source_table'] = table_name
                                    results.append(row_dict)
                                    
                                    if len(results) >= limit:
                                        break
                        except Exception as e:
                            logging.debug(f"Error querying table {table_name}: {e}")
                            continue
                    
                    if len(results) >= limit:
                        break
                        
                except Exception as e:
                    logging.debug(f"Error getting latest data from {table_name}: {e}")
                    continue
            
            tables_checked = min(10, len(tables))
            logging.info(f"Retrieved {len(results)} records from {tables_checked} tables checked")
                    
        except Exception as e:
            logging.error(f"Error getting latest data from {db_name}: {e}", exc_info=True)
        
        if not results:
            logging.warning(f"No data retrieved from database {db_name} (key: {db_key})")
        
        return results

