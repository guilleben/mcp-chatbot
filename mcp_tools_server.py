#!/usr/bin/env python3
"""
MCP Server con herramientas para consultar la base de datos del IPECD.

Este servidor expone herramientas que el LLM puede usar para consultar
datos económicos y sociodemográficos de Corrientes.

Uso:
    python mcp_tools_server.py
    
    O desde servers_config.json:
    {
        "ipecd_tools": {
            "command": "python",
            "args": ["mcp_tools_server.py"]
        }
    }
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Intentar importar MCP
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logging.error("MCP module not available. Install with: pip install mcp")

# Importar cliente de base de datos
try:
    import pymysql
    from dotenv import load_dotenv
    load_dotenv()
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logging.error("pymysql or dotenv not available")


class DatabaseTools:
    """Herramientas para consultar la base de datos del IPECD."""
    
    def __init__(self):
        self.host = os.getenv('HOST_DBB', 'localhost')
        self.port = int(os.getenv('DB_PORT', '3307'))
        self.user = os.getenv('USER_DBB', 'root')
        self.password = os.getenv('PASSWORD_DBB', 'root_dev_password')
        
        # Mapeo de bases de datos (IMPORTANTE: usar los nombres exactos)
        # Los nombres reales de las bases de datos son:
        # - datalake-economico (con guión)
        # - dhw_economico (dhw, no dwh)
        # - dhw_sociodemografico (dhw, no dwh)
        self.databases = {
            'datalake_economico': os.getenv('NAME_DBB_DATALAKE_ECONOMICO', 'datalake-economico'),
            'dwh_economico': os.getenv('NAME_DBB_DWH_ECONOMICO', 'dhw_economico'),
            'dwh_socio': os.getenv('NAME_DBB_DWH_SOCIO', 'dhw_sociodemografico'),
        }
        
        # Log de configuración
        logging.info(f"DatabaseTools initialized with databases: {self.databases}")
    
    def _get_connection(self, database: str = None):
        """Obtiene una conexión a la base de datos."""
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor
        )
    
    def _format_number(self, value: Any) -> str:
        """Formatea números para mejor legibilidad."""
        if value is None:
            return "s/d"
        if isinstance(value, float):
            if abs(value) < 100:
                return f"{value:.2f}"
            return f"{value:,.0f}"
        return str(value)
    
    def _format_date(self, date_value: Any, format_type: str = "full") -> str:
        """
        Formatea fechas en español.
        
        Args:
            date_value: Valor de fecha
            format_type: Tipo de formato:
                - "full": día/mes/año (ej: 01/10/2025)
                - "month_year": Mes Año (ej: Octubre 2025)
                - "short": dd/mm/yy (ej: 01/10/25)
        """
        if date_value is None:
            return "s/d"
        
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                 "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        
        if hasattr(date_value, 'day') and hasattr(date_value, 'month') and hasattr(date_value, 'year'):
            if format_type == "month_year":
                return f"{meses[date_value.month - 1].capitalize()} {date_value.year}"
            elif format_type == "short":
                return f"{date_value.day:02d}/{date_value.month:02d}/{str(date_value.year)[2:]}"
            else:  # full
                return f"{date_value.day:02d}/{date_value.month:02d}/{date_value.year}"
        elif hasattr(date_value, 'month') and hasattr(date_value, 'year'):
            # Solo tiene mes y año
            return f"{meses[date_value.month - 1].capitalize()} {date_value.year}"
        
        # Si es string con formato ISO, convertir
        str_value = str(date_value)
        if '-' in str_value and len(str_value) >= 10:
            try:
                parts = str_value[:10].split('-')
                if len(parts) == 3:
                    year, month, day = parts
                    if format_type == "month_year":
                        return f"{meses[int(month) - 1].capitalize()} {year}"
                    elif format_type == "short":
                        return f"{day}/{month}/{year[2:]}"
                    else:  # full
                        return f"{day}/{month}/{year}"
            except:
                pass
        
        return str_value

    # ==================== TOOL: GET_IPC ====================
    def get_ipc(self, fecha: str = None, region: str = None, categoria: str = None) -> str:
        """
        Obtiene datos del Índice de Precios al Consumidor (IPC).
        
        Args:
            fecha: Fecha en formato YYYY-MM (opcional, por defecto último disponible)
            region: Región (Nacion, NEA, GBA, etc.) (opcional)
            categoria: Categoría del IPC (Alimentos, Transporte, etc.) (opcional)
        
        Returns:
            Información del IPC formateada
        """
        try:
            db_name = self.databases['datalake_economico']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            # Usar query directo a las tablas (evitar vista con definer problemático)
            query = """
                SELECT v.fecha as Fecha, 
                       r.descripcion_region as Region,
                       c.nombre as Categoria,
                       d.nombre as Division,
                       v.valor as Valor, 
                       v.var_mensual as variacion_mensual, 
                       v.var_interanual as variacion_interanual
                FROM ipc_valores v
                LEFT JOIN identificador_regiones r ON v.id_region = r.id_region
                LEFT JOIN ipc_categoria c ON v.id_categoria = c.id_categoria
                LEFT JOIN ipc_division d ON v.id_division = d.id_division
                WHERE v.id_subdivision = 1
            """
            params = []
            
            if fecha:
                query += " AND DATE_FORMAT(v.fecha, '%Y-%m') = %s"
                params.append(fecha)
            else:
                # Último mes disponible
                query += " AND v.fecha = (SELECT MAX(fecha) FROM ipc_valores)"
            
            if region:
                query += " AND r.descripcion_region LIKE %s"
                params.append(f"%{region}%")
            
            if categoria:
                query += " AND (c.nombre LIKE %s OR d.nombre LIKE %s)"
                params.extend([f"%{categoria}%", f"%{categoria}%"])
            
            query += " ORDER BY r.descripcion_region, c.nombre, d.nombre LIMIT 50"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return "No se encontraron datos del IPC para los criterios especificados."
            
            # Formatear resultados
            fecha_dato = self._format_date(results[0]['Fecha'])
            output = f"## 📊 Índice de Precios al Consumidor - {fecha_dato}\n\n"
            
            current_region = None
            for row in results:
                if row['Region'] != current_region:
                    current_region = row['Region']
                    output += f"\n### 🌍 {current_region}\n"
                
                var_mensual = self._format_number(row['variacion_mensual'])
                var_interanual = self._format_number(row['variacion_interanual'])
                
                output += f"- **{row['Categoria']}**: {var_mensual}% mensual | {var_interanual}% interanual\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_ipc: {e}")
            return f"Error al consultar el IPC: {str(e)}"

    # ==================== TOOL: GET_DOLAR ====================
    def get_dolar(self, tipo: str = "blue", fecha: str = None) -> str:
        """
        Obtiene la cotización del dólar.
        
        Args:
            tipo: Tipo de dólar (blue, oficial, mep, ccl)
            fecha: Fecha específica YYYY-MM-DD (opcional, por defecto último disponible)
        
        Returns:
            Cotización del dólar formateada
        """
        try:
            db_name = self.databases['datalake_economico']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            # Seleccionar tabla según tipo
            table_map = {
                'blue': 'dolar_blue',
                'oficial': 'dolar_oficial',
                'mep': 'dolar_mep',
                'ccl': 'dolar_ccl'
            }
            
            table = table_map.get(tipo.lower(), 'dolar_blue')
            
            if fecha:
                query = f"SELECT * FROM {table} WHERE fecha = %s"
                cursor.execute(query, (fecha,))
            else:
                query = f"SELECT * FROM {table} ORDER BY fecha DESC LIMIT 5"
                cursor.execute(query)
            
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return f"No se encontraron datos del dólar {tipo}."
            
            output = f"## 💵 Cotización Dólar {tipo.upper()}\n\n"
            
            for row in results:
                fecha_str = self._format_date(row['fecha'])
                
                if 'compra' in row and 'venta' in row:
                    output += f"**{fecha_str}**: Compra ${self._format_number(row['compra'])} | Venta ${self._format_number(row['venta'])}\n"
                elif 'valor' in row:
                    output += f"**{fecha_str}**: ${self._format_number(row['valor'])}\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_dolar: {e}")
            return f"Error al consultar el dólar: {str(e)}"

    # ==================== TOOL: GET_EMPLEO ====================
    def get_empleo(self, provincia: str = None, tipo: str = "eph") -> str:
        """
        Obtiene datos de empleo y desempleo.
        
        Args:
            provincia: Nombre de la provincia (opcional)
            tipo: Tipo de datos (eph, sipa)
        
        Returns:
            Datos de empleo formateados
        """
        try:
            if tipo.lower() == "eph":
                return self._get_empleo_eph(provincia)
            else:
                return self._get_empleo_sipa(provincia)
                
        except Exception as e:
            logging.error(f"Error en get_empleo: {e}")
            return f"Error al consultar datos de empleo: {str(e)}"
    
    def _get_empleo_eph(self, provincia: str = None) -> str:
        """Obtiene datos de la EPH (Encuesta Permanente de Hogares)."""
        db_name = self.databases['dwh_socio']
        conn = self._get_connection(db_name)
        cursor = conn.cursor()
        
        query = """
            SELECT Region, Aglomerado, Año, Trimestre,
                   `Tasa de Actividad`, `Tasa de Empleo`, `Tasa de desocupación`
            FROM eph_trabajo_tasas
            WHERE 1=1
        """
        params = []
        
        if provincia:
            query += " AND (Aglomerado LIKE %s OR Region LIKE %s)"
            params.extend([f"%{provincia}%", f"%{provincia}%"])
        
        query += " ORDER BY Año DESC, Trimestre DESC LIMIT 20"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return "No se encontraron datos de empleo EPH."
        
        output = "## 👔 Tasas de Empleo y Desempleo (EPH)\n\n"
        
        current_aglomerado = None
        for row in results:
            if row['Aglomerado'] != current_aglomerado:
                current_aglomerado = row['Aglomerado']
                output += f"\n### 📍 {current_aglomerado}\n"
            
            # Las tasas están almacenadas como decimales (0.41 = 41%), multiplicar por 100
            tasa_actividad = row['Tasa de Actividad'] * 100 if row['Tasa de Actividad'] else 0
            tasa_empleo = row['Tasa de Empleo'] * 100 if row['Tasa de Empleo'] else 0
            tasa_desocupacion = row['Tasa de desocupación'] * 100 if row['Tasa de desocupación'] else 0
            
            output += f"**{row['Año']} - {row['Trimestre']}**:\n"
            output += f"  - Tasa de Actividad: {tasa_actividad:.1f}%\n"
            output += f"  - Tasa de Empleo: {tasa_empleo:.1f}%\n"
            output += f"  - Tasa de Desocupación: {tasa_desocupacion:.1f}%\n"
        
        return output
    
    def _get_empleo_sipa(self, provincia: str = None) -> str:
        """Obtiene datos del SIPA."""
        db_name = self.databases['datalake_economico']
        conn = self._get_connection(db_name)
        cursor = conn.cursor()
        
        query = """
            SELECT s.fecha, p.nombre_provincia_indec as provincia,
                   t.descripcion_registro as tipo,
                   s.cantidad_con_estacionalidad, s.cantidad_sin_estacionalidad
            FROM sipa_valores s
            JOIN identificador_provincias p ON s.id_provincia = p.id_provincia_indec
            JOIN sipa_tiporegistro t ON s.id_tipo_registro = t.id_registro
            WHERE 1=1
        """
        params = []
        
        if provincia:
            query += " AND p.nombre_provincia_indec LIKE %s"
            params.append(f"%{provincia}%")
        
        query += " ORDER BY s.fecha DESC LIMIT 30"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return "No se encontraron datos de empleo SIPA."
        
        output = "## 👔 Empleo Registrado (SIPA)\n\n"
        
        for row in results:
            output += f"**{self._format_date(row['fecha'])} - {row['provincia']}**\n"
            output += f"  - Tipo: {row['tipo']}\n"
            output += f"  - Cantidad: {self._format_number(row['cantidad_con_estacionalidad'])}\n"
        
        return output

    # ==================== TOOL: GET_SEMAFORO ====================
    def get_semaforo(self, tipo: str = "interanual") -> str:
        """
        Obtiene el semáforo económico con indicadores clave.
        
        Args:
            tipo: interanual o intermensual
        
        Returns:
            Semáforo económico formateado
        """
        try:
            db_name = self.databases['dwh_economico']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            table = f"semaforo_{tipo.lower()}"
            query = f"SELECT * FROM {table} ORDER BY fecha DESC LIMIT 1"
            
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return f"No se encontraron datos del semáforo {tipo}."
            
            fecha_str = self._format_date(result['fecha'])
            output = f"## 🚦 Semáforo Económico - Variación {tipo.capitalize()} ({fecha_str})\n\n"
            
            indicadores = [
                ('combustible_vendido', '⛽ Combustible vendido'),
                ('patentamiento_0km_auto', '🚗 Patentamiento autos 0km'),
                ('patentamiento_0km_motocicleta', '🏍️ Patentamiento motos 0km'),
                ('pasajeros_salidos_terminal_corrientes', '🚌 Pasajeros terminal'),
                ('pasajeros_aeropuerto_corrientes', '✈️ Pasajeros aeropuerto'),
                ('venta_supermercados_autoservicios_mayoristas', '🛒 Ventas supermercados'),
                ('exportaciones_aduana_corrientes_dolares', '📦 Exportaciones (USD)'),
                ('empleo_privado_registrado_sipa', '👔 Empleo privado SIPA'),
                ('ipicorr', '🏭 IPI Corrientes'),
            ]
            
            for key, label in indicadores:
                if key in result and result[key] is not None:
                    valor = result[key]
                    emoji = "🟢" if valor > 0 else "🔴" if valor < 0 else "🟡"
                    output += f"{emoji} **{label}**: {self._format_number(valor)}%\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_semaforo: {e}")
            return f"Error al consultar el semáforo: {str(e)}"

    # ==================== TOOL: GET_CANASTA_BASICA ====================
    def get_canasta_basica(self) -> str:
        """
        Obtiene datos de la Canasta Básica Alimentaria (CBA) y Total (CBT).
        
        Returns:
            Datos de canasta básica formateados
        """
        try:
            db_name = self.databases['dwh_socio']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            query = """
                SELECT fecha, cba_gba, cbt_gna as cbt_gba, cba_nea, cbt_nea,
                       cba_nea_familia, cbt_nea_familia,
                       vmensual_cba, vinter_cba, vmensual_cbt, vinter_cbt
                FROM correo_cbt_cba
                ORDER BY fecha DESC
                LIMIT 6
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return "No se encontraron datos de la canasta básica."
            
            ultimo = results[0]
            fecha_str = self._format_date(ultimo['fecha'])
            
            output = f"## 🛒 Canasta Básica - {fecha_str}\n\n"
            
            # Mostrar valores actuales
            output += "### Valores por Adulto Equivalente\n\n"
            output += "| Región | CBA | CBT |\n"
            output += "|--------|-----|-----|\n"
            output += f"| **GBA** | ${self._format_number(ultimo['cba_gba'])} | ${self._format_number(ultimo['cbt_gba'])} |\n"
            output += f"| **NEA** | ${self._format_number(ultimo['cba_nea'])} | ${self._format_number(ultimo['cbt_nea'])} |\n"
            
            # Valores familiares NEA
            if ultimo.get('cba_nea_familia') and ultimo.get('cbt_nea_familia'):
                output += f"\n### Valores Familiares (NEA)\n"
                output += f"- **CBA Familia**: ${self._format_number(ultimo['cba_nea_familia'])}\n"
                output += f"- **CBT Familia**: ${self._format_number(ultimo['cbt_nea_familia'])}\n"
            
            # Variaciones
            output += f"\n### Variaciones\n"
            if ultimo.get('vmensual_cba'):
                output += f"- Variación mensual CBA: {self._format_number(ultimo['vmensual_cba'])}%\n"
            if ultimo.get('vinter_cba'):
                output += f"- Variación interanual CBA: {self._format_number(ultimo['vinter_cba'])}%\n"
            if ultimo.get('vmensual_cbt'):
                output += f"- Variación mensual CBT: {self._format_number(ultimo['vmensual_cbt'])}%\n"
            if ultimo.get('vinter_cbt'):
                output += f"- Variación interanual CBT: {self._format_number(ultimo['vinter_cbt'])}%\n"
            
            output += "\n> **CBA** = Canasta Básica Alimentaria (línea de indigencia)\n"
            output += "> **CBT** = Canasta Básica Total (línea de pobreza)\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_canasta_basica: {e}")
            return f"Error al consultar la canasta básica: {str(e)}"

    # ==================== TOOL: GET_ECV ====================
    def get_ecv(self, aglomerado: str = None) -> str:
        """
        Obtiene datos de la Encuesta de Calidad de Vida (ECV).
        Incluye tasas de empleo, trabajo público/privado, salarios promedio.
        
        Args:
            aglomerado: Nombre del aglomerado (opcional, ej: "Corrientes")
        
        Returns:
            Datos de la ECV formateados
        """
        try:
            db_name = self.databases['dwh_socio']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            query = """
                SELECT Aglomerado, Año, Trimestre,
                       `Tasa de Actividad`, `Tasa de Empleo`, `Tasa de desocupación`,
                       `Trabajo Público`, `Trabajo Privado`,
                       `Trabajo Privado Registrado`, `Trabajo Privado No Registrado`,
                       `Salario Promedio Público`, `Salario Promedio Privado`,
                       `Salario Promedio Privado Registrado`, `Salario Promedio Privado No Registrado`
                FROM ecv_trabajo
                WHERE 1=1
            """
            params = []
            
            if aglomerado:
                query += " AND Aglomerado LIKE %s"
                params.append(f"%{aglomerado}%")
            else:
                # Por defecto mostrar Corrientes
                query += " AND Aglomerado LIKE %s"
                params.append("%Corrientes%")
            
            query += " ORDER BY Año DESC, Trimestre DESC LIMIT 8"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return "No se encontraron datos de la Encuesta de Calidad de Vida (ECV)."
            
            output = "## 📋 Encuesta de Calidad de Vida (ECV)\n\n"
            
            for row in results:
                # Multiplicar tasas por 100 para mostrar porcentajes
                tasa_actividad = row['Tasa de Actividad'] * 100 if row['Tasa de Actividad'] else 0
                tasa_empleo = row['Tasa de Empleo'] * 100 if row['Tasa de Empleo'] else 0
                tasa_desocupacion = row['Tasa de desocupación'] * 100 if row['Tasa de desocupación'] else 0
                trabajo_publico = row['Trabajo Público'] * 100 if row['Trabajo Público'] else 0
                trabajo_privado = row['Trabajo Privado'] * 100 if row['Trabajo Privado'] else 0
                priv_registrado = row['Trabajo Privado Registrado'] * 100 if row['Trabajo Privado Registrado'] else 0
                priv_no_registrado = row['Trabajo Privado No Registrado'] * 100 if row['Trabajo Privado No Registrado'] else 0
                
                output += f"### 📍 {row['Aglomerado']} - {row['Año']} {row['Trimestre']}\n\n"
                output += f"**Tasas de Empleo:**\n"
                output += f"- Tasa de Actividad: {tasa_actividad:.1f}%\n"
                output += f"- Tasa de Empleo: {tasa_empleo:.1f}%\n"
                output += f"- Tasa de Desocupación: {tasa_desocupacion:.1f}%\n\n"
                
                output += f"**Composición del Empleo:**\n"
                output += f"- Trabajo Público: {trabajo_publico:.1f}%\n"
                output += f"- Trabajo Privado: {trabajo_privado:.1f}%\n"
                output += f"  - Registrado: {priv_registrado:.1f}%\n"
                output += f"  - No Registrado: {priv_no_registrado:.1f}%\n\n"
                
                output += f"**Salarios Promedio:**\n"
                output += f"- Sector Público: ${self._format_number(row['Salario Promedio Público'])}\n"
                output += f"- Sector Privado: ${self._format_number(row['Salario Promedio Privado'])}\n"
                output += f"  - Registrado: ${self._format_number(row['Salario Promedio Privado Registrado'])}\n"
                output += f"  - No Registrado: ${self._format_number(row['Salario Promedio Privado No Registrado'])}\n\n"
            
            output += "> **ECV** = Encuesta de Calidad de Vida\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_ecv: {e}")
            return f"Error al consultar la ECV: {str(e)}"

    # ==================== TOOL: GET_CENSO ====================
    def get_censo(self, municipio: str = None) -> str:
        """
        Obtiene datos del censo poblacional por municipio.
        
        Args:
            municipio: Nombre del municipio (opcional)
        
        Returns:
            Datos censales formateados
        """
        try:
            db_name = self.databases['dwh_socio']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            query = """
                SELECT DISTINCT municipio, 
                       MAX(poblacion_viv_part_2010) as pob_2010,
                       MAX(poblacion_viv_part_2022) as pob_2022,
                       MAX(var_abs_poblacion_2010_vs_2022) as var_absoluta,
                       MAX(peso_relativo_2022) as peso_relativo_2022,
                       MAX(var_rel_poblacion_2010_vs_2022) as var_relativa
                FROM censo_ipecd_municipios
                WHERE municipio != 'Indeterminado'
            """
            params = []
            
            if municipio:
                query += " AND municipio LIKE %s"
                params.append(f"%{municipio}%")
            
            query += " GROUP BY municipio ORDER BY pob_2022 DESC LIMIT 20"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return "No se encontraron datos del censo."
            
            output = "## 👥 Censo Poblacional 2010 vs 2022\n\n"
            output += "| Municipio | Pob. 2010 | Pob. 2022 | Variación |\n"
            output += "|-----------|-----------|-----------|----------|\n"
            
            for row in results:
                var = f"+{row['var_relativa']:.1f}%" if row['var_relativa'] > 0 else f"{row['var_relativa']:.1f}%"
                output += f"| {row['municipio']} | {self._format_number(row['pob_2010'])} | {self._format_number(row['pob_2022'])} | {var} |\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_censo: {e}")
            return f"Error al consultar el censo: {str(e)}"

    # ==================== TOOL: GET_CENSO_DEPARTAMENTOS ====================
    def get_censo_departamentos(self, departamento: str = None) -> str:
        """
        Obtiene datos del censo poblacional por departamento.
        
        Args:
            departamento: Nombre del departamento (opcional)
        
        Returns:
            Datos censales por departamento formateados
        """
        try:
            db_name = self.databases['dwh_socio']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            # Intentar primero con tabla de departamentos
            try:
                query = """
                    SELECT departamento, 
                           SUM(poblacion_viv_part_2010) as pob_2010,
                           SUM(poblacion_viv_part_2022) as pob_2022
                    FROM censo_ipecd_municipios
                    WHERE municipio != 'Indeterminado'
                """
                params = []
                
                if departamento:
                    query += " AND departamento LIKE %s"
                    params.append(f"%{departamento}%")
                
                query += " GROUP BY departamento ORDER BY pob_2022 DESC LIMIT 25"
                
                cursor.execute(query, params)
                results = cursor.fetchall()
            except:
                # Fallback: agrupar municipios
                query = """
                    SELECT SUBSTRING_INDEX(municipio, ' - ', 1) as departamento,
                           SUM(poblacion_viv_part_2010) as pob_2010,
                           SUM(poblacion_viv_part_2022) as pob_2022
                    FROM censo_ipecd_municipios
                    WHERE municipio != 'Indeterminado'
                    GROUP BY departamento
                    ORDER BY pob_2022 DESC
                    LIMIT 25
                """
                cursor.execute(query)
                results = cursor.fetchall()
            
            conn.close()
            
            if not results:
                return "No se encontraron datos del censo por departamento."
            
            output = "## 👥 Censo Poblacional por Departamento 2010 vs 2022\n\n"
            output += "| Departamento | Pob. 2010 | Pob. 2022 | Variación |\n"
            output += "|--------------|-----------|-----------|----------|\n"
            
            for row in results:
                pob_2010 = row.get('pob_2010') or 0
                pob_2022 = row.get('pob_2022') or 0
                if pob_2010 > 0:
                    var = ((pob_2022 - pob_2010) / pob_2010) * 100
                    var_str = f"+{var:.1f}%" if var > 0 else f"{var:.1f}%"
                else:
                    var_str = "N/A"
                output += f"| {row['departamento']} | {self._format_number(pob_2010)} | {self._format_number(pob_2022)} | {var_str} |\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_censo_departamentos: {e}")
            return f"Error al consultar el censo por departamento: {str(e)}"

    # ==================== TOOL: GET_COMBUSTIBLE ====================
    def get_combustible(self, provincia: str = None, producto: str = None) -> str:
        """
        Obtiene datos de ventas de combustible.
        
        Args:
            provincia: Nombre o ID de la provincia (opcional)
            producto: Tipo de combustible (opcional)
        
        Returns:
            Datos de combustible formateados
        """
        try:
            db_name = self.databases['datalake_economico']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            query = """
                SELECT c.fecha, p.nombre_provincia_indec as provincia, 
                       c.producto, c.cantidad
                FROM combustible c
                JOIN identificador_provincias p ON c.provincia = p.id_provincia_indec
                WHERE 1=1
            """
            params = []
            
            if provincia:
                query += " AND p.nombre_provincia_indec LIKE %s"
                params.append(f"%{provincia}%")
            
            if producto:
                query += " AND c.producto LIKE %s"
                params.append(f"%{producto}%")
            
            query += " ORDER BY c.fecha DESC LIMIT 30"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return "No se encontraron datos de combustible."
            
            output = "## ⛽ Ventas de Combustible\n\n"
            output += "| Fecha | Provincia | Producto | Cantidad |\n"
            output += "|-------|-----------|----------|----------|\n"
            
            for row in results:
                fecha = row.get('fecha', 'N/A')
                provincia = row.get('provincia', 'N/A')
                producto = row.get('producto', 'N/A')
                cantidad = self._format_number(row.get('cantidad', 0))
                output += f"| {fecha} | {provincia} | {producto} | {cantidad} |\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_combustible: {e}")
            return f"Error al consultar combustible: {str(e)}"

    # ==================== TOOL: GET_PATENTAMIENTOS ====================
    def get_patentamientos(self, provincia: str = None, tipo: str = None) -> str:
        """
        Obtiene datos de patentamiento de vehículos (DNRPA).
        
        Args:
            provincia: Nombre de la provincia (opcional)
            tipo: Tipo de vehículo: auto, moto (opcional)
        
        Returns:
            Datos de patentamientos formateados
        """
        try:
            db_name = self.databases['datalake_economico']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            # id_vehiculo: 1=Automóviles, 2=Motovehículos
            query = """
                SELECT d.fecha, p.nombre_provincia_indec as provincia, 
                       CASE d.id_vehiculo WHEN 1 THEN 'Automóviles' ELSE 'Motovehículos' END as tipo,
                       d.cantidad
                FROM dnrpa d
                LEFT JOIN identificador_provincias p ON d.id_provincia_indec = p.id_provincia_indec
                WHERE 1=1
            """
            params = []
            
            if provincia:
                query += " AND p.nombre_provincia_indec LIKE %s"
                params.append(f"%{provincia}%")
            
            if tipo:
                if 'auto' in tipo.lower():
                    query += " AND d.id_vehiculo = 1"
                elif 'moto' in tipo.lower():
                    query += " AND d.id_vehiculo = 2"
            
            query += " ORDER BY d.fecha DESC LIMIT 30"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return "No se encontraron datos de patentamientos."
            
            output = "## 🚗 Patentamientos de Vehículos 0km (DNRPA)\n\n"
            output += "| Fecha | Provincia | Tipo | Cantidad |\n"
            output += "|-------|-----------|------|----------|\n"
            
            for row in results:
                fecha = self._format_date(row.get('fecha'))
                prov = row.get('provincia', 'N/A')
                tipo_v = row.get('tipo', 'N/A')
                cantidad = self._format_number(row.get('cantidad', 0))
                output += f"| {fecha} | {prov} | {tipo_v} | {cantidad} |\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_patentamientos: {e}")
            return f"Error al consultar patentamientos: {str(e)}"

    # ==================== TOOL: GET_AEROPUERTOS ====================
    def get_aeropuertos(self, aeropuerto: str = None) -> str:
        """
        Obtiene datos de pasajeros en aeropuertos (ANAC).
        
        Args:
            aeropuerto: Nombre del aeropuerto (opcional)
        
        Returns:
            Datos de pasajeros formateados
        """
        try:
            db_name = self.databases['datalake_economico']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            query = """
                SELECT fecha, aeropuerto, cantidad as pasajeros
                FROM anac
                WHERE 1=1
            """
            params = []
            
            if aeropuerto:
                query += " AND aeropuerto LIKE %s"
                params.append(f"%{aeropuerto}%")
            
            query += " ORDER BY fecha DESC LIMIT 20"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return "No se encontraron datos de aeropuertos."
            
            output = "## ✈️ Pasajeros en Aeropuertos (ANAC)\n\n"
            output += "| Fecha | Aeropuerto | Pasajeros |\n"
            output += "|-------|------------|----------|\n"
            
            for row in results:
                fecha = self._format_date(row.get('fecha'))
                aero = row.get('aeropuerto', 'N/A')
                pasajeros = self._format_number(int(row.get('pasajeros', 0)))
                output += f"| {fecha} | {aero} | {pasajeros} |\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_aeropuertos: {e}")
            return f"Error al consultar aeropuertos: {str(e)}"

    # ==================== TOOL: GET_OEDE ====================
    def get_oede(self, provincia: str = "Corrientes", categoria: str = None) -> str:
        """
        Obtiene datos del Observatorio de Empleo y Dinámica Empresarial (OEDE).
        
        Args:
            provincia: Nombre de la provincia (por defecto: Corrientes)
            categoria: Categoría de actividad (opcional)
        
        Returns:
            Datos de empleo OEDE formateados
        """
        try:
            db_name = self.databases['datalake_economico']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            query = """
                SELECT o.fecha, p.nombre_provincia_indec as provincia,
                       d.nombre as categoria, o.valor
                FROM OEDE_valores o
                LEFT JOIN identificador_provincias p ON o.id_provincia = p.id_provincia_indec
                LEFT JOIN OEDE_diccionario d ON o.id_categoria = d.id_categoria 
                    AND o.id_subcategoria = d.id_subcategoria
                WHERE 1=1
            """
            params = []
            
            # Por defecto filtrar por Corrientes (IPECD es de Corrientes)
            if provincia:
                query += " AND p.nombre_provincia_indec LIKE %s"
                params.append(f"%{provincia}%")
            
            if categoria:
                query += " AND d.nombre LIKE %s"
                params.append(f"%{categoria}%")
            
            query += " ORDER BY o.fecha DESC LIMIT 30"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return "No se encontraron datos del OEDE."
            
            output = "## 📊 Observatorio de Empleo (OEDE)\n\n"
            output += "Datos del Observatorio de Empleo y Dinámica Empresarial del Ministerio de Trabajo.\n\n"
            output += "| Fecha | Provincia | Categoría | Valor |\n"
            output += "|-------|-----------|-----------|-------|\n"
            
            for row in results:
                fecha = self._format_date(row.get('fecha'))
                prov = row.get('provincia', 'N/A')
                cat = row.get('categoria', 'N/A')
                if cat and len(str(cat)) > 30:
                    cat = str(cat)[:30] + "..."
                valor = self._format_number(row.get('valor', 0))
                output += f"| {fecha} | {prov} | {cat} | {valor} |\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_oede: {e}")
            return f"Error al consultar OEDE: {str(e)}"

    # ==================== TOOL: GET_POBREZA ====================
    def get_pobreza(self, region: str = None) -> str:
        """
        Obtiene datos de Canasta Básica Total (CBT) y Canasta Básica Alimentaria (CBA)
        para medir líneas de pobreza e indigencia.
        
        Args:
            region: Región específica (GBA, NEA, etc.)
        
        Returns:
            Datos de canastas formateados
        """
        try:
            db_name = self.databases['dwh_socio']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            query = """
                SELECT fecha, 
                       cba_gba, cbt_gna as cbt_gba,
                       cba_nea, cbt_nea,
                       cba_nea_familia, cbt_nea_familia,
                       vmensual_cba, vinter_cba
                FROM correo_cbt_cba
                ORDER BY fecha DESC LIMIT 12
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return "No se encontraron datos de pobreza/indigencia."
            
            output = "## 📉 Líneas de Pobreza e Indigencia\n\n"
            output += "**CBA** (Canasta Básica Alimentaria): Define la línea de **indigencia**\n"
            output += "**CBT** (Canasta Básica Total): Define la línea de **pobreza**\n\n"
            
            output += "### Región NEA (Noreste Argentino)\n\n"
            output += "| Fecha | CBA (Adulto) | CBT (Adulto) | CBA (Familia) | CBT (Familia) |\n"
            output += "|-------|--------------|--------------|---------------|---------------|\n"
            
            for row in results:
                fecha = self._format_date(row.get('fecha'), format_type="month_year")
                cba_nea = f"${self._format_number(row.get('cba_nea', 0) or 0)}"
                cbt_nea = f"${self._format_number(row.get('cbt_nea', 0) or 0)}"
                cba_fam = f"${self._format_number(row.get('cba_nea_familia', 0) or 0)}"
                cbt_fam = f"${self._format_number(row.get('cbt_nea_familia', 0) or 0)}"
                output += f"| {fecha} | {cba_nea} | {cbt_nea} | {cba_fam} | {cbt_fam} |\n"
            
            output += "\n> **Familia tipo**: 4 integrantes (2 adultos + 2 menores)\n"
            output += "> Una familia es **indigente** si no puede cubrir la CBA\n"
            output += "> Una familia es **pobre** si no puede cubrir la CBT"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_pobreza: {e}")
            return f"Error al consultar datos de pobreza: {str(e)}"

    # ==================== TOOL: GET_EMAE ====================
    def get_emae(self, categoria: str = None) -> str:
        """
        Obtiene datos del Estimador Mensual de Actividad Económica (EMAE).
        
        Args:
            categoria: Categoría de actividad económica (opcional)
        
        Returns:
            Datos del EMAE formateados
        """
        try:
            db_name = self.databases['datalake_economico']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            query = """
                SELECT e.fecha, c.categoria_descripcion as categoria, e.valor
                FROM emae e
                LEFT JOIN emae_categoria c ON e.sector_productivo = c.id_categoria
                WHERE 1=1
            """
            params = []
            
            if categoria:
                query += " AND c.categoria_descripcion LIKE %s"
                params.append(f"%{categoria}%")
            
            query += " ORDER BY e.fecha DESC LIMIT 30"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return "No se encontraron datos del EMAE."
            
            output = "## 📈 Estimador Mensual de Actividad Económica (EMAE)\n\n"
            output += "El EMAE mide la evolución mensual de la actividad económica del país.\n\n"
            output += "| Fecha | Sector | Valor |\n"
            output += "|-------|--------|-------|\n"
            
            for row in results:
                fecha = self._format_date(row.get('fecha'))
                cat = row.get('categoria', 'General')
                if cat and len(str(cat)) > 35:
                    cat = str(cat)[:35] + "..."
                valor = self._format_number(row.get('valor', 0))
                output += f"| {fecha} | {cat} | {valor} |\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_emae: {e}")
            return f"Error al consultar EMAE: {str(e)}"

    # ==================== TOOL: GET_PBG ====================
    def get_pbg(self, tipo: str = "anual", sector: str = None) -> str:
        """
        Obtiene datos del Producto Bruto Geográfico (PBG) de Corrientes.
        
        Args:
            tipo: Tipo de datos (anual, trimestral, desglosado)
            sector: Sector económico (opcional)
        
        Returns:
            Datos del PBG formateados
        """
        try:
            db_name = self.databases['datalake_economico']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            if tipo.lower() == "trimestral":
                query = """
                    SELECT Año, Trimestre, Actividad, Valor, Variacion
                    FROM pbg_valor_trimestral 
                    ORDER BY Año DESC, Trimestre DESC 
                    LIMIT 20
                """
                cursor.execute(query)
                results = cursor.fetchall()
                conn.close()
                
                if not results:
                    return "No se encontraron datos del PBG trimestral."
                
                output = "## 🏭 PBG Trimestral - Corrientes\n\n"
                output += "| Año | Trim | Actividad | Valor | Variación |\n"
                output += "|-----|------|-----------|-------|----------|\n"
                
                for row in results:
                    año = row.get('Año', 'N/A')
                    trim = row.get('Trimestre', 'N/A')
                    actividad = row.get('Actividad', 'General')
                    if actividad and len(str(actividad)) > 20:
                        actividad = str(actividad)[:20] + "..."
                    valor = self._format_number(row.get('Valor', 0))
                    var = self._format_number(row.get('Variacion'))
                    output += f"| {año} | {trim} | {actividad} | {valor} | {var}% |\n"
                
                return output
                
            elif tipo.lower() == "desglosado":
                query = """
                    SELECT año, descripcion, valor, variacion_interanual
                    FROM pbg_anual_desglosado
                    WHERE 1=1
                """
                params = []
                
                if sector:
                    query += " AND descripcion LIKE %s"
                    params.append(f"%{sector}%")
                
                query += " ORDER BY año DESC, valor DESC LIMIT 30"
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                conn.close()
                
                if not results:
                    return "No se encontraron datos del PBG desglosado."
                
                output = "## 🏭 PBG Desglosado - Corrientes\n\n"
                output += "| Año | Sector | Valor | Var. Interanual |\n"
                output += "|-----|--------|-------|----------------|\n"
                
                for row in results:
                    año = row.get('año', 'N/A')
                    sector_name = row.get('descripcion', 'N/A')
                    if sector_name and len(str(sector_name)) > 30:
                        sector_name = str(sector_name)[:30] + "..."
                    valor = self._format_number(row.get('valor', 0))
                    var = self._format_number(row.get('variacion_interanual'))
                    output += f"| {año} | {sector_name} | {valor} | {var}% |\n"
                
                return output
            
            else:  # anual por defecto
                query = """
                    SELECT Año, Actividad, Valor, Variacion
                    FROM pbg_valor_anual 
                    WHERE 1=1
                """
                params = []
                
                if sector:
                    query += " AND Actividad LIKE %s"
                    params.append(f"%{sector}%")
                
                query += " ORDER BY Año DESC, Valor DESC LIMIT 30"
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                conn.close()
                
                if not results:
                    return "No se encontraron datos del PBG."
                
                output = "## 🏭 Producto Bruto Geográfico (PBG) - Corrientes\n\n"
                output += "El PBG mide el valor de la producción de bienes y servicios de la provincia.\n\n"
                output += "| Año | Actividad | Valor | Variación |\n"
                output += "|-----|-----------|-------|----------|\n"
                
                for row in results:
                    año = row.get('Año', 'N/A')
                    actividad = row.get('Actividad', 'N/A')
                    if actividad and len(str(actividad)) > 25:
                        actividad = str(actividad)[:25] + "..."
                    valor = self._format_number(row.get('Valor', 0))
                    var = self._format_number(row.get('Variacion'))
                    output += f"| {año} | {actividad} | {valor} | {var}% |\n"
                
                return output
            
        except Exception as e:
            logging.error(f"Error en get_pbg: {e}")
            return f"Error al consultar PBG: {str(e)}"

    # ==================== TOOL: GET_SALARIOS ====================
    def get_salarios(self, tipo: str = "smvm") -> str:
        """
        Obtiene datos de salarios e índices salariales.
        
        Args:
            tipo: Tipo de salario (smvm=Salario Mínimo, ripte=RIPTE, indicadores)
        
        Returns:
            Datos de salarios formateados
        """
        try:
            db_name = self.databases['datalake_economico']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            if tipo.lower() == "ripte":
                query = "SELECT fecha, valor FROM ripte ORDER BY fecha DESC LIMIT 12"
                cursor.execute(query)
                results = cursor.fetchall()
                
                if not results:
                    conn.close()
                    return "No se encontraron datos del RIPTE."
                
                output = "## 💰 RIPTE (Remuneración Imponible Promedio)\n\n"
                output += "El RIPTE es el índice que se usa para actualizar jubilaciones y pensiones.\n\n"
                output += "| Fecha | Valor |\n"
                output += "|-------|-------|\n"
                
                for row in results:
                    output += f"| {self._format_date(row.get('fecha'))} | ${self._format_number(row.get('valor', 0))} |\n"
                    
            elif tipo.lower() == "indicadores":
                query = """
                    SELECT periodo, is_sector_privado_registrado, is_sector_publico, 
                           is_total_registrado, is_indice_total
                    FROM indicadores_salarios ORDER BY periodo DESC LIMIT 12
                """
                cursor.execute(query)
                results = cursor.fetchall()
                
                if not results:
                    conn.close()
                    return "No se encontraron índices de salarios."
                
                output = "## 📊 Índices de Salarios\n\n"
                output += "| Fecha | S. Público | S. Privado | Total Reg. | Índice Total |\n"
                output += "|-------|------------|------------|------------|---------------|\n"
                
                for row in results:
                    fecha = self._format_date(row.get('periodo'), format_type="month_year")
                    pub = self._format_number(row.get('is_sector_publico', 0))
                    priv = self._format_number(row.get('is_sector_privado_registrado', 0))
                    total_reg = self._format_number(row.get('is_total_registrado', 0))
                    total = self._format_number(row.get('is_indice_total', 0))
                    output += f"| {fecha} | {pub} | {priv} | {total_reg} | {total} |\n"
                    
            else:  # smvm por defecto
                query = "SELECT fecha, salario_mvm_mensual, salario_mvm_diario, salario_mvm_hora FROM salario_mvm ORDER BY fecha DESC LIMIT 12"
                cursor.execute(query)
                results = cursor.fetchall()
                
                if not results:
                    conn.close()
                    return "No se encontraron datos del Salario Mínimo."
                
                output = "## 💵 Salario Mínimo Vital y Móvil (SMVM)\n\n"
                output += "| Fecha | Mensual | Diario | Por Hora |\n"
                output += "|-------|---------|--------|----------|\n"
                
                for row in results:
                    fecha = self._format_date(row.get('fecha'), format_type="month_year")
                    mensual = f"${self._format_number(row.get('salario_mvm_mensual', 0))}"
                    diario = f"${self._format_number(row.get('salario_mvm_diario', 0))}"
                    hora = f"${self._format_number(row.get('salario_mvm_hora', 0))}"
                    output += f"| {fecha} | {mensual} | {diario} | {hora} |\n"
            
            conn.close()
            return output
            
        except Exception as e:
            logging.error(f"Error en get_salarios: {e}")
            return f"Error al consultar salarios: {str(e)}"

    # ==================== TOOL: GET_SUPERMERCADOS ====================
    def get_supermercados(self, provincia: str = None) -> str:
        """
        Obtiene datos de facturación de supermercados.
        
        Args:
            provincia: Provincia específica (opcional)
        
        Returns:
            Datos de supermercados formateados
        """
        try:
            db_name = self.databases['datalake_economico']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            query = """
                SELECT s.fecha, p.nombre_provincia_indec as provincia,
                       s.total_facturacion, s.bebidas, s.almacen, s.lacteos, s.carnes
                FROM supermercado_encuesta s
                LEFT JOIN identificador_provincias p ON s.id_provincia_indec = p.id_provincia_indec
                WHERE 1=1
            """
            params = []
            
            if provincia:
                query += " AND p.nombre_provincia_indec LIKE %s"
                params.append(f"%{provincia}%")
            
            query += " ORDER BY s.fecha DESC LIMIT 20"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return "No se encontraron datos de supermercados."
            
            output = "## 🛒 Facturación de Supermercados\n\n"
            output += "| Fecha | Provincia | Total | Bebidas | Almacén | Lácteos | Carnes |\n"
            output += "|-------|-----------|-------|---------|---------|---------|--------|\n"
            
            for row in results:
                fecha = self._format_date(row.get('fecha'))
                prov = row.get('provincia', 'N/A')
                if prov and len(str(prov)) > 12:
                    prov = str(prov)[:12] + "..."
                total = f"${self._format_number(row.get('total_facturacion', 0))}"
                bebidas = self._format_number(row.get('bebidas', 0))
                almacen = self._format_number(row.get('almacen', 0))
                lacteos = self._format_number(row.get('lacteos', 0))
                carnes = self._format_number(row.get('carnes', 0))
                output += f"| {fecha} | {prov} | {total} | {bebidas} | {almacen} | {lacteos} | {carnes} |\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_supermercados: {e}")
            return f"Error al consultar supermercados: {str(e)}"

    # ==================== TOOL: GET_CONSTRUCCION ====================
    def get_construccion(self, tipo: str = "puestos") -> str:
        """
        Obtiene datos de la industria de la construcción (IERIC).
        
        Args:
            tipo: Tipo de dato (puestos, ingresos, actividad)
        
        Returns:
            Datos de construcción formateados
        """
        try:
            db_name = self.databases['datalake_economico']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            if tipo.lower() == "ingresos":
                query = "SELECT * FROM ieric_ingreso ORDER BY fecha DESC LIMIT 20"
                title = "Ingresos en Construcción"
            elif tipo.lower() == "actividad":
                query = "SELECT * FROM ieric_actividad ORDER BY fecha DESC LIMIT 20"
                title = "Actividad Empresarial en Construcción"
            else:
                query = "SELECT * FROM ieric_puestos_trabajo ORDER BY fecha DESC LIMIT 20"
                title = "Puestos de Trabajo en Construcción"
            
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return f"No se encontraron datos de {title.lower()}."
            
            output = f"## 🏗️ {title} (IERIC)\n\n"
            output += "Datos del Instituto de Estadística y Registro de la Industria de la Construcción.\n\n"
            
            # Determinar columnas disponibles
            if results:
                cols = list(results[0].keys())
                # Filtrar columnas relevantes
                relevant_cols = [c for c in cols if c.lower() not in ['id', 'created_at', 'updated_at']][:5]
                
                header = "| " + " | ".join([c.replace('_', ' ').title() for c in relevant_cols]) + " |\n"
                separator = "|" + "|".join(["-------" for _ in relevant_cols]) + "|\n"
                output += header + separator
                
                for row in results:
                    values = []
                    for col in relevant_cols:
                        val = row.get(col, 'N/A')
                        if col.lower() == 'fecha':
                            val = self._format_date(val)
                        elif isinstance(val, (int, float)):
                            val = self._format_number(val)
                        values.append(str(val)[:20] if val else 'N/A')
                    output += "| " + " | ".join(values) + " |\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_construccion: {e}")
            return f"Error al consultar construcción: {str(e)}"

    # ==================== TOOL: GET_IPC_CORRIENTES ====================
    def get_ipc_corrientes(self) -> str:
        """
        Obtiene el IPC específico de Corrientes (IPICorr) con variaciones.
        
        Returns:
            IPC de Corrientes formateado
        """
        try:
            db_name = self.databases['datalake_economico']
            conn = self._get_connection(db_name)
            cursor = conn.cursor()
            
            query = """
                SELECT fecha, valor, var_mensual, var_interanual
                FROM ipicorr
                ORDER BY fecha DESC
                LIMIT 12
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return "No se encontraron datos del IPC de Corrientes."
            
            output = "## 📊 IPC de Corrientes (IPICorr)\n\n"
            output += "Índice de Precios al Consumidor específico para la ciudad de Corrientes.\n\n"
            output += "| Fecha | Valor | Var. Mensual | Var. Interanual |\n"
            output += "|-------|-------|--------------|------------------|\n"
            
            for row in results:
                fecha = self._format_date(row.get('fecha'), format_type="month_year")
                valor = self._format_number(row.get('valor', 0))
                var_m = self._format_number(row.get('var_mensual'))
                var_i = self._format_number(row.get('var_interanual'))
                output += f"| {fecha} | {valor} | {var_m}% | {var_i}% |\n"
            
            # Resumen
            ultimo = results[0]
            output += f"\n📌 **Última variación mensual:** {self._format_number(ultimo.get('var_mensual'))}%\n"
            output += f"📌 **Variación interanual:** {self._format_number(ultimo.get('var_interanual'))}%"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en get_ipc_corrientes: {e}")
            return f"Error al consultar IPC de Corrientes: {str(e)}"

    # ==================== TOOL: SEARCH_DATABASE ====================
    def search_database(self, query: str, database: str = None) -> str:
        """
        Búsqueda general en la base de datos.
        
        Args:
            query: Término de búsqueda
            database: Base de datos específica (opcional)
        
        Returns:
            Resultados de la búsqueda formateados
        """
        try:
            results = []
            
            # Determinar bases de datos a buscar
            if database and database in self.databases:
                dbs_to_search = {database: self.databases[database]}
            else:
                dbs_to_search = self.databases
            
            for db_key, db_name in dbs_to_search.items():
                try:
                    conn = self._get_connection(db_name)
                    cursor = conn.cursor()
                    
                    # Obtener tablas
                    cursor.execute("SHOW TABLES")
                    tables = [t[f'Tables_in_{db_name}'] for t in cursor.fetchall()]
                    
                    for table in tables[:10]:  # Limitar tablas a buscar
                        try:
                            # Obtener columnas de texto
                            cursor.execute(f"DESCRIBE `{table}`")
                            columns = cursor.fetchall()
                            text_columns = [c['Field'] for c in columns 
                                          if 'char' in c['Type'].lower() or 'text' in c['Type'].lower()]
                            
                            if text_columns:
                                where_clauses = [f"`{col}` LIKE %s" for col in text_columns[:3]]
                                search_query = f"""
                                    SELECT * FROM `{table}` 
                                    WHERE {' OR '.join(where_clauses)}
                                    LIMIT 5
                                """
                                params = [f"%{query}%"] * len(where_clauses)
                                cursor.execute(search_query, params)
                                
                                for row in cursor.fetchall():
                                    row['_table'] = table
                                    row['_database'] = db_key
                                    results.append(row)
                                    
                                if len(results) >= 20:
                                    break
                        except:
                            continue
                    
                    conn.close()
                    
                except Exception as e:
                    logging.warning(f"Error buscando en {db_name}: {e}")
                    continue
                
                if len(results) >= 20:
                    break
            
            if not results:
                return f"No se encontraron resultados para '{query}'."
            
            output = f"## 🔍 Resultados de búsqueda: '{query}'\n\n"
            output += f"Se encontraron {len(results)} resultados.\n\n"
            
            for i, row in enumerate(results[:10], 1):
                table = row.pop('_table', 'desconocida')
                db = row.pop('_database', 'desconocida')
                
                output += f"### Resultado {i}\n"
                for key, value in list(row.items())[:5]:
                    if value is not None and not key.startswith('_'):
                        output += f"- **{key}**: {self._format_number(value)}\n"
                output += "\n"
            
            return output
            
        except Exception as e:
            logging.error(f"Error en search_database: {e}")
            return f"Error en la búsqueda: {str(e)}"


# ==================== MCP SERVER ====================
if MCP_AVAILABLE:
    
    # Crear instancia del servidor MCP
    app = Server("ipecd-tools")
    db_tools = DatabaseTools()
    
    @app.list_tools()
    async def list_tools() -> list[Tool]:
        """Lista todas las herramientas disponibles."""
        return [
            Tool(
                name="get_ipc",
                description="Obtiene datos del Índice de Precios al Consumidor (IPC). Incluye variaciones mensuales e interanuales por región y categoría.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "fecha": {
                            "type": "string",
                            "description": "Fecha en formato YYYY-MM (opcional, por defecto último disponible)"
                        },
                        "region": {
                            "type": "string",
                            "description": "Región: Nacion, NEA, GBA, Cuyo, etc. (opcional)"
                        },
                        "categoria": {
                            "type": "string",
                            "description": "Categoría del IPC: Alimentos, Transporte, Vivienda, etc. (opcional)"
                        }
                    }
                }
            ),
            Tool(
                name="get_dolar",
                description="Obtiene la cotización del dólar en Argentina (blue, oficial, MEP, CCL).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tipo": {
                            "type": "string",
                            "description": "Tipo de dólar: blue, oficial, mep, ccl",
                            "default": "blue"
                        },
                        "fecha": {
                            "type": "string",
                            "description": "Fecha específica YYYY-MM-DD (opcional)"
                        }
                    }
                }
            ),
            Tool(
                name="get_empleo",
                description="Obtiene datos de empleo y desempleo de Argentina. Fuentes: EPH (Encuesta Permanente de Hogares) y SIPA (Sistema Integrado Previsional Argentino).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "provincia": {
                            "type": "string",
                            "description": "Nombre de la provincia o aglomerado (opcional)"
                        },
                        "tipo": {
                            "type": "string",
                            "description": "Fuente de datos: eph o sipa",
                            "default": "eph"
                        }
                    }
                }
            ),
            Tool(
                name="get_semaforo",
                description="Obtiene el semáforo económico de Corrientes con indicadores clave: combustible, patentamientos, pasajeros, ventas, exportaciones, empleo.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tipo": {
                            "type": "string",
                            "description": "Tipo de variación: interanual o intermensual",
                            "default": "interanual"
                        }
                    }
                }
            ),
            Tool(
                name="get_censo",
                description="Obtiene datos del censo poblacional de Corrientes, comparando 2010 vs 2022 por municipio.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "municipio": {
                            "type": "string",
                            "description": "Nombre del municipio (opcional, si no se especifica muestra los más poblados)"
                        }
                    }
                }
            ),
            Tool(
                name="get_combustible",
                description="Obtiene datos de ventas de combustible por provincia y tipo de producto.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "provincia": {
                            "type": "string",
                            "description": "Nombre de la provincia (opcional)"
                        },
                        "producto": {
                            "type": "string",
                            "description": "Tipo de combustible: nafta, gasoil, etc. (opcional)"
                        }
                    }
                }
            ),
            Tool(
                name="search_database",
                description="Búsqueda general en todas las bases de datos del IPECD. Útil cuando no sabes exactamente qué herramienta usar.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Término de búsqueda"
                        },
                        "database": {
                            "type": "string",
                            "description": "Base de datos específica: datalake_economico, dwh_economico, dwh_socio (opcional)"
                        }
                    },
                    "required": ["query"]
                }
            ),
        ]
    
    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Ejecuta una herramienta y devuelve el resultado."""
        try:
            if name == "get_ipc":
                result = db_tools.get_ipc(
                    fecha=arguments.get("fecha"),
                    region=arguments.get("region"),
                    categoria=arguments.get("categoria")
                )
            elif name == "get_dolar":
                result = db_tools.get_dolar(
                    tipo=arguments.get("tipo", "blue"),
                    fecha=arguments.get("fecha")
                )
            elif name == "get_empleo":
                result = db_tools.get_empleo(
                    provincia=arguments.get("provincia"),
                    tipo=arguments.get("tipo", "eph")
                )
            elif name == "get_semaforo":
                result = db_tools.get_semaforo(
                    tipo=arguments.get("tipo", "interanual")
                )
            elif name == "get_censo":
                result = db_tools.get_censo(
                    municipio=arguments.get("municipio")
                )
            elif name == "get_combustible":
                result = db_tools.get_combustible(
                    provincia=arguments.get("provincia"),
                    producto=arguments.get("producto")
                )
            elif name == "search_database":
                result = db_tools.search_database(
                    query=arguments.get("query", ""),
                    database=arguments.get("database")
                )
            else:
                result = f"Herramienta desconocida: {name}"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            logging.error(f"Error ejecutando {name}: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def main():
        """Punto de entrada principal del servidor MCP."""
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    if not MCP_AVAILABLE:
        print("Error: MCP module not available. Install with: pip install mcp")
        sys.exit(1)
    
    if not DB_AVAILABLE:
        print("Error: Database modules not available. Install with: pip install pymysql python-dotenv")
        sys.exit(1)
    
    asyncio.run(main())

