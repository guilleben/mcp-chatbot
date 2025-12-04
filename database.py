"""Database client module for MySQL connections using SQLAlchemy and Connection Pooling."""
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import re

import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
import pandas as pd


class DatabaseClient:
    """Manages database connections using SQLAlchemy with connection pooling."""
    
    def __init__(self, host: str, port: int, user: str, password: str, databases: Dict[str, str]):
        """Initialize database client.
        
        Args:
            host: Database host
            port: Database port
            user: Database user
            password: Database password
            databases: Dictionary of database names by key
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.databases = databases
        
        # Cache de engines (Connection Pooling)
        self._engines: Dict[str, sqlalchemy.Engine] = {}
        
        # Cache para estructura de tablas (evita consultas repetidas)
        self._table_cache: Dict[str, List[str]] = {}
        self._column_cache: Dict[str, List[str]] = {}
        
        # Cache para resultados de búsqueda (mejora tiempos de respuesta)
        self._search_cache: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}
        self._cache_ttl = 300  # 5 minutos de TTL para caché de búsquedas
        
        logging.info("DatabaseClient initialized with SQLAlchemy pooling")

    def _get_engine(self, db_name: str) -> sqlalchemy.Engine:
        """Get or create a SQLAlchemy engine for the specified database."""
        if db_name not in self._engines:
            # Construir URL de conexión
            connection_string = f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{db_name}"
            
            # Crear engine con pool configurado (optimizado para velocidad)
            self._engines[db_name] = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=5,           # Mantener 5 conexiones abiertas
                max_overflow=10,       # Permitir hasta 10 extra en picos
                pool_recycle=3600,     # Reciclar cada hora
                pool_pre_ping=True,    # Verificar conexión antes de usar
                connect_args={
                    "connect_timeout": 5,  # Timeout de conexión de 5 segundos
                    "read_timeout": 10,     # Timeout de lectura de 10 segundos
                    "write_timeout": 10     # Timeout de escritura de 10 segundos
                }
            )
            logging.info(f"Created new engine pool for database: {db_name}")
            
        return self._engines[db_name]
    
    def connect(self, database: Optional[str] = None):
        """Get a connection from the pool.
        
        Args:
            database: Database name to connect to.
            
        Returns:
            SQLAlchemy connection object.
        """
        if not database:
            # Si no se especifica BD, usar la primera disponible o fallar
            if not self.databases:
                raise ValueError("No databases configured")
            database = list(self.databases.values())[0]
            
        engine = self._get_engine(database)
        return engine.connect()
    
    def _get_tables(self, db_name: str, conn) -> List[str]:
        """Obtener lista de tablas con caché."""
        if db_name not in self._table_cache:
            result = conn.execute(text("SHOW TABLES"))
            # El nombre de la columna es Tables_in_dbname
            self._table_cache[db_name] = [row[0] for row in result.fetchall()]
        return self._table_cache[db_name]
    
    def _get_columns(self, db_name: str, table: str, conn) -> List[str]:
        """Obtener columnas de una tabla con caché."""
        cache_key = f"{db_name}.{table}"
        if cache_key not in self._column_cache:
            result = conn.execute(text(f"DESCRIBE `{table}`"))
            # DESCRIBE devuelve: Field, Type, Null, Key, Default, Extra
            # En SQLAlchemy result.mappings() permite acceso por nombre
            self._column_cache[cache_key] = [row._mapping['Field'] for row in result.fetchall()]
        return self._column_cache[cache_key]
    
    def _is_relevant_table(self, table: str, search_terms: List[str]) -> bool:
        """Verificar si una tabla es relevante para la búsqueda."""
        table_lower = table.lower()
        
        # Mapeo de sinónimos y variaciones comunes
        synonym_map = {
            'internet': ['internet', 'conectividad', 'acceso', 'online', 'red'],
            'agua': ['agua', 'beber', 'cocinar', 'potable'],
            'cloaca': ['cloaca', 'alcantarillado', 'saneamiento'],
            'salud': ['salud', 'cobertura', 'obra social', 'pami'],
            'educacion': ['educacion', 'escolar', 'asistencia', 'clima educativo'],
            'vivienda': ['vivienda', 'hogar', 'inmat', 'calidad'],
            'empleo': ['empleo', 'trabajo', 'ocupacion', 'laboral'],
            'sexo': ['sexo', 'genero', 'masculino', 'femenino'],
            'censo': ['censo', 'poblacion', 'demografico'],
            'patentamiento': ['patentamiento', 'vehiculo', 'auto', 'moto', 'dnrpa'],
            'combustible': ['combustible', 'nafta', 'gasoil', 'gasolina'],
            'inflacion': ['inflacion', 'ipc', 'precios', 'indice'],
            'pbg': ['pbg', 'producto bruto', 'geografico', 'economico']
        }
        
        # Expandir términos de búsqueda con sinónimos
        expanded_terms = set(search_terms)
        for term in search_terms:
            for key, synonyms in synonym_map.items():
                if term in synonyms or any(syn in term for syn in synonyms):
                    expanded_terms.update(synonyms)
        
        # Verificar coincidencia directa
        if any(term in table_lower for term in expanded_terms):
            return True
        
        # Verificar coincidencia parcial (palabras dentro de términos)
        for term in expanded_terms:
            if len(term) > 3 and term in table_lower:
                return True
        
        return False
    
    def _get_cache_key(self, query: str, limit: int, max_results: int) -> str:
        """Generar clave de caché para una consulta."""
        cache_string = f"{query.lower().strip()}:{limit}:{max_results}"
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def _get_cached_results(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Obtener resultados del caché si están disponibles y no han expirado."""
        if cache_key in self._search_cache:
            results, timestamp = self._search_cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                logging.debug(f"Cache hit for query: {cache_key[:16]}...")
                return results
            else:
                # Cache expirado, eliminarlo
                del self._search_cache[cache_key]
        return None
    
    def _set_cached_results(self, cache_key: str, results: List[Dict[str, Any]]) -> None:
        """Guardar resultados en el caché."""
        # Limpiar caché si tiene más de 100 entradas (evitar uso excesivo de memoria)
        if len(self._search_cache) > 100:
            # Eliminar las entradas más antiguas
            sorted_cache = sorted(self._search_cache.items(), key=lambda x: x[1][1])
            for key, _ in sorted_cache[:20]:  # Eliminar las 20 más antiguas
                del self._search_cache[key]
        
        self._search_cache[cache_key] = (results, time.time())
        logging.debug(f"Cached results for query: {cache_key[:16]}... ({len(results)} results)")
    
    def query_specific_table(self, db_key: str, table_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Consultar una tabla específica directamente.
        
        Args:
            db_key: Clave de la base de datos (ej: "datalake_economico")
            table_name: Nombre de la tabla
            limit: Número máximo de resultados
            
        Returns:
            Lista de registros de la tabla
        """
        results = []
        try:
            # Obtener el nombre real de la base de datos
            db_name = self.databases.get(db_key)
            if not db_name:
                logging.warning(f"Database key {db_key} not found in configuration")
                return []
            
            with self.connect(db_name) as conn:
                # Buscar columna de fecha para ordenar si existe
                columns = self._get_columns(db_name, table_name, conn)
                date_columns = [c for c in columns if 'fecha' in c.lower() or 'date' in c.lower() or 'año' in c.lower() or 'ano' in c.lower()]
                
                # Construir query
                if date_columns:
                    order_by_col = date_columns[0]
                    query = text(f"SELECT * FROM `{table_name}` ORDER BY `{order_by_col}` DESC LIMIT :limit")
                else:
                    query = text(f"SELECT * FROM `{table_name}` LIMIT :limit")
                
                result = conn.execute(query, {'limit': limit})
                
                for row in result.fetchall():
                    row_dict = dict(row._mapping)
                    row_dict['_source_db'] = db_name
                    row_dict['_source_table'] = table_name
                    results.append(row_dict)
                
                logging.info(f"Query specific table {db_name}.{table_name}: {len(results)} results")
                
        except Exception as e:
            logging.error(f"Error querying specific table {db_key}.{table_name}: {e}")
        
        return results
    
    def search(self, query: str, limit: int = 3, max_results: int = 15, timeout: int = 3) -> List[Dict[str, Any]]:
        """Search across all databases for information matching the query (optimized for speed).
        
        Args:
            query: Search query string
            limit: Maximum number of results per table (reduced for speed)
            max_results: Maximum total results to return (reduced for speed)
            timeout: Maximum seconds to spend searching per database (reduced for speed)
            
        Returns:
            List of search results from all databases
        """
        # Verificar caché primero
        cache_key = self._get_cache_key(query, limit, max_results)
        cached_results = self._get_cached_results(cache_key)
        if cached_results is not None:
            return cached_results
        
        # Detectar si el query especifica una tabla específica (formato: "database.table")
        table_match = re.match(r'^([^.]+)\.([^.]+)$', query.strip())
        if table_match:
            db_key_or_name = table_match.group(1)
            table_name = table_match.group(2)
            
            # Intentar encontrar la clave de la base de datos
            db_key = None
            for key, db_name in self.databases.items():
                if key == db_key_or_name or db_name == db_key_or_name:
                    db_key = key
                    break
            
            if db_key:
                logging.info(f"Detected specific table query: {db_key}.{table_name}")
                results = self.query_specific_table(db_key, table_name, limit=max_results)
                if results:
                    self._set_cached_results(cache_key, results)
                    return results
        
        results = []
        # Extraer todos los términos significativos (optimizado)
        common_words = {'el', 'la', 'los', 'las', 'de', 'del', 'en', 'un', 'una', 'y', 'o', 'que', 'para', 'por', 'con', 'sin'}
        search_terms = [term.lower() for term in query.lower().split() if term.lower() not in common_words and len(term) > 2]
        
        if not search_terms:
            search_terms = [term.lower() for term in query.lower().split()[:3]]  # Reducido de 4 a 3
        
        if not search_terms:
            return results
        
        databases_to_search = list(self.databases.items())
        
        for db_key, db_name in databases_to_search:
            if not db_name or len(results) >= max_results:
                break
                
            start_time = time.time()
            try:
                # Usar context manager para asegurar que la conexión vuelve al pool
                with self.connect(db_name) as conn:
                    tables = self._get_tables(db_name, conn)
                    
                    if not tables:
                        continue
                    
                    # Optimización: buscar solo en tablas relevantes, máximo 5 tablas por BD
                    # Primero buscar por nombre de tabla
                    relevant_tables = [t for t in tables if self._is_relevant_table(t, search_terms)]
                    
                    # Si no encontramos tablas relevantes, buscar también en nombres de columnas
                    if not relevant_tables:
                        try:
                            for table in tables[:10]:  # Revisar hasta 10 tablas para encontrar columnas relevantes
                                columns = self._get_columns(db_name, table, conn)
                                column_names = ' '.join(columns).lower()
                                if any(term in column_names for term in search_terms):
                                    relevant_tables.append(table)
                                    if len(relevant_tables) >= 3:  # Máximo 3 tablas por coincidencia de columnas
                                        break
                        except Exception as e:
                            logging.debug(f"Error checking columns for relevance: {e}")
                    
                    other_tables = [t for t in tables if t not in relevant_tables]
                    tables_to_search = (relevant_tables + other_tables)[:5]  # Reducido de 10 a 5
                    
                    for table in tables_to_search:
                        if len(results) >= max_results or (time.time() - start_time) > timeout:
                            break
                            
                        try:
                            columns = self._get_columns(db_name, table, conn)
                            text_columns = [c for c in columns if c.lower() not in 
                                          ['id', 'created_at', 'updated_at', 'deleted_at', 'timestamp']]
                            
                            if not text_columns:
                                continue
                            
                            # Optimización: buscar solo en las primeras 3 columnas más relevantes
                            search_columns = text_columns[:3]  # Reducido de 5 a 3
                            
                            where_conditions = []
                            params = {}
                            
                            # Optimización: usar solo los primeros 2 términos más importantes
                            for i, term in enumerate(search_terms[:2]):  # Reducido de 4 a 2
                                term_conditions = []
                                for col in search_columns:
                                    param_name = f"term_{i}_{col}"
                                    term_conditions.append(f"`{col}` LIKE :{param_name}")
                                    params[param_name] = f"%{term}%"
                                
                                if term_conditions:
                                    where_conditions.append(f"({' OR '.join(term_conditions)})")
                            
                            if not where_conditions and search_terms:
                                for col in search_columns[:2]:  # Reducido de 3 a 2
                                    param_name = f"term_0_{col}"
                                    where_conditions.append(f"`{col}` LIKE :{param_name}")
                                    params[param_name] = f"%{search_terms[0]}%"
                            
                            if where_conditions:
                                # Optimización: usar ORDER BY para obtener resultados más recientes primero
                                where_clause = " OR ".join(where_conditions[:2])  # Máximo 2 condiciones
                                # Intentar ordenar por fecha si existe una columna de fecha
                                order_by = ""
                                date_columns = [c for c in columns if 'fecha' in c.lower() or 'date' in c.lower() or 'año' in c.lower() or 'ano' in c.lower()]
                                if date_columns:
                                    order_by = f" ORDER BY `{date_columns[0]}` DESC"
                                
                                search_query = text(f"""
                                    SELECT * FROM `{table}` 
                                    WHERE {where_clause}
                                    {order_by}
                                    LIMIT :limit
                                """)
                                params['limit'] = limit
                                
                                result_proxy = conn.execute(search_query, params)
                                # Convertir a lista de dicts
                                table_results = [dict(row._mapping) for row in result_proxy.fetchall()]
                                
                                if table_results:
                                    for row in table_results:
                                        row['_source_db'] = db_name
                                        row['_source_table'] = table
                                        results.append(row)
                                        
                                        if len(results) >= max_results:
                                            break
                        except Exception as e:
                            logging.debug(f"Error searching table {table} in {db_name}: {e}")
                            continue
            except Exception as e:
                logging.warning(f"Error searching database {db_name}: {e}")
                continue
            
            if len(results) >= max_results:
                break
        
        final_results = results[:max_results]
        
        # Guardar en caché
        self._set_cached_results(cache_key, final_results)
        
        logging.info(f"Database search completed: {len(final_results)} results found in {time.time() - start_time:.2f}s")
        return final_results
    
    def get_database_structure(self) -> Dict[str, Any]:
        """Obtener estructura de todas las bases de datos."""
        structure = {}
        
        for db_key, db_name in self.databases.items():
            if not db_name:
                continue
                
            try:
                with self.connect(db_name) as conn:
                    tables = self._get_tables(db_name, conn)
                    structure[db_name] = {}
                    
                    for table in tables[:20]:
                        try:
                            columns = self._get_columns(db_name, table, conn)
                            try:
                                result = conn.execute(text(f"SELECT * FROM `{table}` LIMIT 1"))
                                row = result.fetchone()
                                sample = dict(row._mapping) if row else None
                            except:
                                sample = None
                            
                            structure[db_name][table] = {
                                'columns': columns,
                                'sample': sample
                            }
                        except Exception as e:
                            logging.debug(f"Error getting structure for table {table}: {e}")
                            continue
            except Exception as e:
                logging.warning(f"Error getting structure for database {db_name}: {e}")
                continue
        
        return structure
    
    def search_with_fallback(self, query: str, limit: int = 3, max_results: int = 15, timeout: int = 3) -> List[Dict[str, Any]]:
        """Búsqueda mejorada con múltiples estrategias de fallback (optimizada para velocidad)."""
        
        # Estrategia 1: Búsqueda normal (con límites reducidos)
        results = self.search(query, limit, max_results, timeout)
        
        if results:
            return results
        
        # Estrategia 2: Si no encuentra nada, buscar solo el primer término significativo (con timeout reducido)
        search_terms = [term.lower() for term in query.lower().split() if len(term) > 2]
        if search_terms and len(search_terms) > 1:
            logging.info(f"No results with full query, trying single term: {search_terms[0]}")
            results = self.search(search_terms[0], limit * 2, max_results, timeout // 2)  # Timeout reducido a la mitad
            if results:
                return results
        
        # Estrategia 3: Buscar en nombres de tablas y columnas
        logging.info("Trying to find relevant tables by name...")
        structure = self.get_database_structure()
        relevant_tables = []
        
        query_lower = query.lower()
        for db_name, tables in structure.items():
            for table_name, table_info in tables.items():
                if any(term in table_name.lower() for term in query_lower.split()):
                    relevant_tables.append((db_name, table_name, table_info))
        
        if relevant_tables:
            logging.info(f"Found {len(relevant_tables)} relevant tables, searching...")
            for db_name, table_name, table_info in relevant_tables[:10]:
                try:
                    with self.connect(db_name) as conn:
                        text_cols = [c for c in table_info['columns'] 
                                    if c.lower() not in ['id', 'created_at', 'updated_at', 'deleted_at']]
                        
                        if text_cols:
                            conditions = []
                            params = {}
                            search_terms_clean = [t for t in query_lower.split() if len(t) > 2]
                            
                            for i, term in enumerate(search_terms_clean[:4]):
                                term_conditions = []
                                for col in text_cols[:8]:
                                    param_name = f"term_{i}_{col}"
                                    term_conditions.append(f"`{col}` LIKE :{param_name}")
                                    params[param_name] = f"%{term}%"
                                if term_conditions:
                                    conditions.append(f"({' OR '.join(term_conditions)})")
                            
                            if conditions:
                                search_query = text(f"""
                                    SELECT * FROM `{table_name}` 
                                    WHERE {' OR '.join(conditions[:4])}
                                    LIMIT :limit
                                """)
                                params['limit'] = limit * 5
                                
                                result = conn.execute(search_query, params)
                                table_results = [dict(row._mapping) for row in result.fetchall()]
                                
                                if table_results:
                                    for row in table_results:
                                        row['_source_db'] = db_name
                                        row['_source_table'] = table_name
                                        results.append(row)
                                        if len(results) >= max_results:
                                            break
                                
                                # Estrategia 2: Muestras
                                if not table_results and len(results) < max_results:
                                    try:
                                        result = conn.execute(text(f"SELECT * FROM `{table_name}` LIMIT :limit"), {'limit': limit * 2})
                                        sample_results = [dict(row._mapping) for row in result.fetchall()]
                                        if sample_results:
                                            for row in sample_results[:5]:
                                                row['_source_db'] = db_name
                                                row['_source_table'] = table_name
                                                row['_is_sample'] = True
                                                results.append(row)
                                                if len(results) >= max_results:
                                                    break
                                    except:
                                        pass
                                
                                if len(results) >= max_results:
                                    break
                except Exception as e:
                    logging.debug(f"Error in fallback search for {table_name}: {e}")
                    continue
        
        return results[:max_results]
