"""IPC (Índice de Precios al Consumidor) logic module."""
import pandas as pd
import logging
from typing import Optional, Dict, Any
from datetime import datetime

class IPCLogic:
    """Maneja la lógica de negocio para el IPC."""
    
    def __init__(self, db_client):
        self.db_client = db_client
        
    def _load_data(self) -> pd.DataFrame:
        """Carga los datos del IPC desde la base de datos."""
        try:
            # Usar la vista optimizada del legacy bot
            query = "SELECT * FROM datalake_economico.vista_ipc_bot_reglas"
            
            # Ejecutar query usando el cliente de BD
            # Nota: Asumimos que datalake_economico está configurada en el cliente
            # Si no, deberíamos buscar el nombre correcto en db_client.databases
            db_name = self.db_client.databases.get('datalake_economico', 'datalake_economico')
            
            results = self.db_client.execute_query(db_name, query)
            df = pd.DataFrame(results)
            
            if df.empty:
                return pd.DataFrame()
                
            # Normalizar columnas
            df = df.rename(columns={
                "fecha": "Fecha",
                "valor": "Valor",
                "variacion_mensual": "variacion_mensual",
                "variacion_interanual": "variacion_interanual",
            })
            
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
            return df
            
        except Exception as e:
            logging.error(f"Error loading IPC data: {e}")
            return pd.DataFrame()

    def get_latest_ipc(self) -> str:
        """Obtiene el último valor del IPC formateado."""
        df = self._load_data()
        if df.empty:
            return "⚠️ No se pudieron cargar los datos del IPC."
            
        ultima_fecha = df["Fecha"].max()
        df_last = df[df["Fecha"] == ultima_fecha].copy()
        
        if df_last.empty:
            return "⚠️ No hay datos para la última fecha."
            
        meses = ["enero","febrero","marzo","abril","mayo","junio","julio",
                 "agosto","septiembre","octubre","noviembre","diciembre"]
        nombre_mes = f"{meses[ultima_fecha.month-1].capitalize()} {ultima_fecha.year}"
        
        def bloque_region(nombre_region: str, id_region: int) -> Optional[str]:
            dfr = df_last[df_last["id_region"] == id_region].copy()
            if dfr.empty:
                return None

            # Nivel general primero
            dfr["is_headline"] = (
                (dfr["id_categoria"]==1) & (dfr["id_division"]==1) & (dfr["id_subdivision"]==1)
            )
            dfr = dfr.sort_values(
                by=["is_headline","id_categoria","id_division","id_subdivision"],
                ascending=[False, True, True, True]
            )

            lineas = [f"🌍 *{nombre_region.upper()}*"]
            for _, r in dfr.iterrows():
                etiqueta = "Nivel general" if r["is_headline"] else str(r["Categoria"])
                vm = f"{r['variacion_mensual']:.1f}%" if pd.notna(r["variacion_mensual"]) else "s/d"
                va = f"{r['variacion_interanual']:.1f}%" if pd.notna(r["variacion_interanual"]) else "s/d"
                lineas.append(f"• *{etiqueta}*: {vm} (mensual) | {va} (interanual)")
            return "\n".join(lineas)

        partes = [f"📅 *IPC — Últimas variaciones ({nombre_mes})*\n"]
        
        # Primero Nación, luego NEA
        for nombre_region, id_region in [("Nacion", 1), ("NEA", 5)]:
            bloque = bloque_region(nombre_region, id_region)
            if bloque:
                partes.append(bloque)
                partes.append("")

        return "\n".join(partes).strip()

    def get_ipc_by_date(self, date_str: str) -> str:
        """Obtiene datos de IPC para una fecha específica (YYYY-MM)."""
        try:
            fecha = pd.to_datetime(date_str + "-01")
        except:
            return "❌ Fecha inválida. Usa el formato YYYY-MM."
            
        df = self._load_data()
        df = df[df["Fecha"] == fecha]
        
        if df.empty:
            return f"⚠️ No hay datos disponibles para {date_str}."
            
        meses = ["enero","febrero","marzo","abril","mayo","junio","julio",
                 "agosto","septiembre","octubre","noviembre","diciembre"]
        nombre_mes = f"{meses[fecha.month-1].capitalize()} {fecha.year}"
        
        mensaje = f"📅 *IPC - {nombre_mes}*\n\n"
        
        categorias = sorted(df["Categoria"].unique())
        for categoria in categorias:
            mensaje += f"📌 *{categoria}*\n"
            for region in ["NEA", "Nacion"]:
                row = df[(df["Region"] == region) & (df["Categoria"] == categoria)]
                if not row.empty:
                    r = row.iloc[0]
                    mensaje += f"🌍 {region}\n"
                    mensaje += f"  - Variación mensual: *{r['variacion_mensual']:.2f}%*\n"
                    mensaje += f"  - Variación interanual: *{r['variacion_interanual']:.2f}%*\n"
            mensaje += "\n"
            
        return mensaje.strip()
