"""Diccionario de nombres amigables para campos de la base de datos."""

# Mapeo de nombres técnicos a nombres amigables
FIELD_FRIENDLY_NAMES = {
    # Campos comunes
    'codigo': 'Código',
    'fecha': 'Fecha',
    'año': 'Año',
    'ano': 'Año',
    'mes': 'Mes',
    'trimestre': 'Trimestre',
    'provincia': 'Provincia',
    'departamento': 'Departamento',
    'municipio': 'Municipio',
    'region': 'Región',
    'aglomerado': 'Aglomerado',
    
    # Datos sociales
    'total_vivienda': 'Total de Viviendas',
    'total_viviendas': 'Total de Viviendas',
    'total_poblacion': 'Total de Población',
    'con_internet': 'Con Internet',
    'sin_internet': 'Sin Internet',
    'red_publica': 'Red Pública',
    'bomba_motor': 'Bomba a Motor',
    'bomba_manual': 'Bomba Manual',
    'pozo_sin_bomba': 'Pozo sin Bomba',
    'camara_septica_con_pozo_ciego': 'Cámara Séptica con Pozo Ciego',
    'solo_pozo_ciego': 'Solo Pozo Ciego',
    'hoyo_excavacion_etc': 'Hoyo/Excavación',
    'asiste': 'Asiste',
    'no_asiste': 'No Asiste',
    'nunca_asistio': 'Nunca Asistió',
    'obra_social_prepaga_pami': 'Obra Social/Prepaga/PAMI',
    'programas_estatales_salud': 'Programas Estatales de Salud',
    'sin_obra_social_ni_plan_estatal': 'Sin Obra Social ni Plan Estatal',
    'electricidad': 'Electricidad',
    'gas_red': 'Gas por Red',
    'gas_tubo_o_zepelin': 'Gas en Tubo o Zepelín',
    'gas_garrafa': 'Gas en Garrafa',
    'leña_carbon': 'Leña o Carbón',
    'calidad_1': 'Calidad 1',
    'calidad_2': 'Calidad 2',
    'calidad_3': 'Calidad 3',
    'calidad_4': 'Calidad 4',
    'ceramica_mosaico_baldosa_etc': 'Cerámica/Mosaico/Baldosa',
    'carpeta_contrapiso_ladrillo': 'Carpeta/Contrapiso/Ladrillo',
    'tierra_ladrillosuelto': 'Tierra/Ladrillo Suelto',
    'servicio_domestico': 'Servicio Doméstico',
    'empleado_obrero': 'Empleado/Obrero',
    'cuenta_propia': 'Cuenta Propia',
    'patron_empleador': 'Patrón/Empleador',
    'clima_muy_bajo': 'Clima Educativo Muy Bajo',
    'clima_bajo': 'Clima Educativo Bajo',
    'clima_medio': 'Clima Educativo Medio',
    'clima_alto': 'Clima Educativo Alto',
    'clima_muy_alto': 'Clima Educativo Muy Alto',
    
    # Datos económicos
    'valor': 'Valor',
    'precio': 'Precio',
    'cantidad': 'Cantidad',
    'producto': 'Producto',
    'aeropuerto': 'Aeropuerto',
    'patentamiento_0km_auto': 'Patentamiento Autos 0km',
    'patentamiento_0km_motocicleta': 'Patentamiento Motos 0km',
    'combustible_vendido': 'Combustible Vendido',
    'pasajeros_salidos_terminal_corrientes': 'Pasajeros Terminal Corrientes',
    'pasajeros_aeropuerto_corrientes': 'Pasajeros Aeropuerto Corrientes',
    'exportaciones_aduana_corrientes_dolares': 'Exportaciones (USD)',
    'exportaciones_aduana_corrientes_toneladas': 'Exportaciones (Toneladas)',
    'variacion_mensual': 'Variación Mensual',
    'variacion_interanual': 'Variación Interanual',
    'variacion_relativa': 'Variación Relativa',
    'pbg': 'Producto Bruto Geográfico',
    'pbi': 'Producto Bruto Interno',
    'inflacion': 'Inflación',
    'ipc': 'Índice de Precios al Consumidor',
    'tasa_desempleo': 'Tasa de Desempleo',
    'tasa_actividad': 'Tasa de Actividad',
    'tasa_empleo': 'Tasa de Empleo',
    
    # Censo
    'poblacion_2010': 'Población 2010',
    'poblacion_2022': 'Población 2022',
    'poblacion_viv_part_2010': 'Población 2010',
    'poblacion_viv_part_2022': 'Población 2022',
    'var_abs_poblacion_2010_vs_2022': 'Variación Absoluta 2010-2022',
    'peso_relativo_2022': 'Peso Relativo 2022',
    'acceso_internet': 'Acceso a Internet',
    'division_geo': 'División Geográfica',
}

def get_friendly_name(field_name: str) -> str:
    """Obtener nombre amigable para un campo.
    
    Args:
        field_name: Nombre técnico del campo
        
    Returns:
        Nombre amigable del campo
    """
    field_lower = field_name.lower().strip()
    
    # Buscar coincidencia exacta
    if field_lower in FIELD_FRIENDLY_NAMES:
        return FIELD_FRIENDLY_NAMES[field_lower]
    
    # Buscar coincidencia parcial
    for key, friendly_name in FIELD_FRIENDLY_NAMES.items():
        if key in field_lower or field_lower in key:
            return friendly_name
    
    # Si no hay coincidencia, formatear el nombre técnico
    # Remover prefijos comunes
    field_clean = field_lower
    for prefix in ['id_', 'cod_', 'num_', 'total_', 'cant_', 'var_', 'p_']:
        if field_clean.startswith(prefix):
            field_clean = field_clean[len(prefix):]
            break
    
    # Convertir snake_case a título
    field_title = field_clean.replace('_', ' ').title()
    
    return field_title

