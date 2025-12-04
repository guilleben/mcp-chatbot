"""Employment (EPH Mercado de Trabajo) logic module."""
import pandas as pd
import logging
from typing import Optional, Dict, Any

class EmpleoLogic:
    """Maneja la lógica de negocio para Mercado de Trabajo (EPH)."""
    
    def __init__(self, db_client):
        self.db_client = db_client
        
    def _load_data(self) -> pd.DataFrame:
        """Carga los datos de EPH desde la base de datos."""
        try:
            query = "SELECT * FROM eph_trabajo_tasas"
            
            # Buscar nombre correcto de la BD dwh_socio
            db_name = self.db_client.databases.get('dwh_socio', 'dwh_socio')
            
            results = self.db_client.execute_query(db_name, query)
            df = pd.DataFrame(results)
            
            if df.empty:
                return pd.DataFrame()
                
            # Limpieza básica (similar a DataProcessor del legacy)
            if 'Trimestre' in df.columns:
                df['Trimestre'] = df['Trimestre'].astype(str).str.strip()
            
            # Asegurar tipos numéricos y escalar a porcentaje si es necesario
            numeric_cols = ['Tasa de Actividad', 'Tasa de Empleo', 'Tasa de desocupación']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    # Si el máximo es pequeño (ej. < 1.5), asumir que es decimal y convertir a %
                    if df[col].max() <= 1.5:
                        df[col] = df[col] * 100
            
            return df
            
        except Exception as e:
            logging.error(f"Error loading Employment data: {e}")
            return pd.DataFrame()

    def get_latest_employment_data(self) -> str:
        """Obtiene los últimos datos de empleo formateados."""
        df = self._load_data()
        if df.empty:
            return "⚠️ No se pudieron cargar los datos de mercado de trabajo."
            
        # Encontrar última fecha (Año + Trimestre)
        # Asumimos que hay columna Fecha o Año/Trimestre
        if 'Fecha' in df.columns:
            ultima_fecha = df['Fecha'].max()
            df_ultimos = df[df['Fecha'] == ultima_fecha]
        else:
            # Fallback si no hay columna Fecha parseada
            max_anio = df['Año'].max()
            df_anio = df[df['Año'] == max_anio]
            # Ordenar por trimestre (asumiendo formato "X Trimestre")
            # Esto es simplificado, idealmente parsear trimestre
            df_ultimos = df_anio  # Tomamos todo el año si no podemos ordenar trimestres fácil
        
        if df_ultimos.empty:
            return "⚠️ No hay datos disponibles."
            
        row = df_ultimos.iloc[0]
        anio = row.get('Año', '')
        trimestre = row.get('Trimestre', '')
        
        mensaje = f"📅 *Mercado de Trabajo: {trimestre} {anio}*\n\n"
        
        for _, row in df_ultimos.iterrows():
            region = row.get('Region', 'Desconocida')
            aglomerado = row.get('Aglomerado', '')
            if pd.isna(aglomerado): aglomerado = "Total"
            
            actividad = row.get('Tasa de Actividad')
            empleo = row.get('Tasa de Empleo')
            desocupacion = row.get('Tasa de desocupación')
            
            if pd.notna(actividad):
                mensaje += f"🏙️ *{region}* ({aglomerado})\n"
                mensaje += f"• Tasa de Actividad: *{actividad:.1f}%*\n"
                mensaje += f"• Tasa de Empleo: *{empleo:.1f}%*\n"
                mensaje += f"• Tasa de Desocupación: *{desocupacion:.1f}%*\n\n"
                
        return mensaje.strip()

    def get_employment_by_period(self, year: int, quarter: str = None) -> str:
        """Obtiene datos de empleo para un año y trimestre específico."""
        df = self._load_data()
        if df.empty:
            return "⚠️ No se pudieron cargar los datos."
            
        df_filtered = df[df['Año'] == year]
        
        if quarter:
            # Búsqueda flexible de trimestre
            df_filtered = df_filtered[df_filtered['Trimestre'].str.contains(quarter, case=False, na=False)]
            
        if df_filtered.empty:
            return f"⚠️ No se encontraron datos para {year} {quarter if quarter else ''}."
            
        mensaje = f"📅 *Mercado de Trabajo: {year}*\n\n"
        
        # Agrupar por trimestre si hay varios
        trimestres = df_filtered['Trimestre'].unique()
        
        for trim in trimestres:
            mensaje += f"🗓️ *{trim}*\n"
            df_trim = df_filtered[df_filtered['Trimestre'] == trim]
            
            for _, row in df_trim.iterrows():
                region = row.get('Region', '')
                aglomerado = row.get('Aglomerado', '')
                if pd.isna(aglomerado): aglomerado = "Total"
                
                actividad = row.get('Tasa de Actividad')
                desocupacion = row.get('Tasa de desocupación')
                
                if pd.notna(actividad):
                    mensaje += f"  🏙️ {region} ({aglomerado}): Actividad *{actividad:.1f}%* | Desocupación *{desocupacion:.1f}%*\n"
            mensaje += "\n"
            
        return mensaje.strip()
