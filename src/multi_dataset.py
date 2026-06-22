import os
import pandas as pd
import psycopg
from typing import Any
from dataset_manager import list_stored_tables, get_dataset_table_info_by_name
from database import load_db_config

def get_all_available_datasets(connection=None):
    """
    Obtiene metadatos completos de todos los datasets disponibles en la BD.
    Ya no busca archivos Excel, solo trabaja con tablas en BD subidas por usuarios.
    """
    conn = connection
    available_datasets = {}
    
    # Obtener todas las tablas de la BD
    stored_tables = list_stored_tables(conn)
    
    if not stored_tables:
        print("📁 No hay datasets disponibles en la BD")
        print("💡 Los usuarios deben subir documentos vía /api/documents/upload")
        return available_datasets
    
    print(f"📊 {len(stored_tables)} dataset(s) encontrado(s) en BD")
    
    for table_name in stored_tables:
        table_info = get_dataset_table_info_by_name(table_name, conn)
        if table_info:
            available_datasets[table_name] = {
                "source": "database",
                "table_name": table_name,
                "friendly_name": get_friendly_dataset_name(table_name),
                "columns": table_info["columns"][:10],  # Primeras 10 columnas
                "row_count": table_info["row_count"],
                "main_columns": identify_key_columns(table_info["columns"]),
                "description": generate_dataset_description(table_name, table_info["columns"]),
                "keywords": generate_dataset_keywords(table_name, table_info["columns"])
            }
        else:
            print(f"⚠️ No se pudo obtener información de la tabla: {table_name}")
    
    return available_datasets

def get_friendly_dataset_name(table_name):
    """Convierte nombres de tabla a nombres amigables"""
    name_mapping = {
        "dataset_rides": "Dataset de Viajes NCR",
        "crocodile_dataset": "Dataset de Cocodrilos",
        "ncr_ride_bookings": "Reservas de Viajes NCR"
    }
    return name_mapping.get(table_name, table_name.replace("_", " ").title())

def identify_key_columns(columns):
    """Identifica las columnas más importantes basándose en nombres comunes"""
    key_patterns = {
        "id": ["id", "identifier", "key"],
        "date": ["date", "time", "created", "updated", "timestamp"],
        "location": ["location", "city", "address", "place", "destination"],
        "amount": ["price", "cost", "amount", "value", "fare", "payment"],
        "category": ["type", "category", "method", "status", "class"],
        "user": ["user", "customer", "client", "passenger", "driver"]
    }
    
    identified = []
    for col in columns[:8]:  # Solo primeras 8 columnas
        col_lower = col.lower()
        for category, patterns in key_patterns.items():
            if any(pattern in col_lower for pattern in patterns):
                identified.append(f"{col} ({category})")
                break
        else:
            identified.append(col)
    
    return identified[:5]  # Máximo 5 columnas clave

def generate_dataset_description(table_name, columns):
    """Genera una descripción inteligente del dataset"""
    descriptions = {
        "dataset_rides": "Contiene información de viajes y reservas de transporte, incluyendo fechas, ubicaciones, costos y métodos de pago",
        "crocodile_dataset": "Dataset biológico con información sobre cocodrilos, posiblemente incluyendo medidas, ubicaciones y características",
        "ncr_ride_bookings": "Sistema de reservas de viajes con detalles de pasajeros, rutas, precios y estados de booking"
    }
    
    if table_name in descriptions:
        return descriptions[table_name]
    
    # Generar descripción automática basada en columnas
    col_hints = []
    columns_lower = [c.lower() for c in columns]
    
    if any("date" in c or "time" in c for c in columns_lower):
        col_hints.append("información temporal")
    if any("price" in c or "cost" in c or "amount" in c for c in columns_lower):
        col_hints.append("datos financieros")
    if any("location" in c or "city" in c for c in columns_lower):
        col_hints.append("datos geográficos")
    if any("user" in c or "customer" in c for c in columns_lower):
        col_hints.append("información de usuarios")
    
    if col_hints:
        return f"Dataset que incluye {', '.join(col_hints)}"
    else:
        return f"Dataset con {len(columns)} columnas de datos"

def generate_dataset_keywords(table_name, columns):
    """Genera palabras clave para identificación automática"""
    keywords = [table_name.replace("_", " ")]
    
    # Agregar keywords basados en nombre
    if "ride" in table_name or "booking" in table_name:
        keywords.extend(["viajes", "transporte", "reservas", "rides", "bookings"])
    if "crocodile" in table_name:
        keywords.extend(["cocodrilos", "animales", "biología", "crocodiles"])
    
    # Agregar keywords basados en columnas
    col_keywords = []
    for col in columns[:10]:
        col_lower = col.lower()
        if "payment" in col_lower:
            col_keywords.extend(["pago", "payment"])
        if "vehicle" in col_lower:
            col_keywords.extend(["vehículo", "vehicle"])
        if "date" in col_lower:
            col_keywords.extend(["fecha", "date"])
        if "location" in col_lower or "city" in col_lower:
            col_keywords.extend(["ubicación", "location"])
    
    keywords.extend(list(set(col_keywords)))
    return keywords

def get_semantic_descriptions_from_db(connection=None):
    """
    Recupera las descripciones semánticas de todas las tablas desde la BD.
    Retorna un diccionario {table_name: semantic_description}
    """
    conn = connection
    if conn is None:
        try:
            db_config = load_db_config()
            connection_string = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
            conn = psycopg.connect(connection_string)
            should_close = True
        except Exception as e:
            print(f"⚠️ Error conectando para obtener descripciones: {e}")
            return {}
    else:
        should_close = False
    
    descriptions = {}
    
    try:
        with conn.cursor() as cursor:
            # Obtener todas las tablas que tienen columna semantic_description
            all_tables = list_stored_tables(conn)
            stored_tables = [t for t in all_tables if t not in ["chats"]]
            
            for table_name in stored_tables:
                try:
                    # Obtener la descripción desde la primera fila (todas tienen la misma)
                    query = f"""
                        SELECT semantic_description 
                        FROM public.{table_name} 
                        WHERE semantic_description IS NOT NULL 
                        LIMIT 1
                    """
                    cursor.execute(query)
                    result = cursor.fetchone()
                    
                    if result and result[0]:
                        descriptions[table_name] = result[0]
                        print(f"📖 Descripción recuperada para '{table_name}'")
                except Exception as e:
                    print(f"⚠️ Error obteniendo descripción de {table_name}: {e}")
                    # Fallback: intentar obtener desde comentario de tabla
                    try:
                        comment_query = """
                            SELECT obj_description(oid) 
                            FROM pg_class 
                            WHERE relname = %s AND relnamespace = 'public'::regnamespace
                        """
                        cursor.execute(comment_query, (table_name,))
                        comment_result = cursor.fetchone()
                        if comment_result and comment_result[0]:
                            descriptions[table_name] = comment_result[0]
                    except:
                        pass
        
        return descriptions
        
    except Exception as e:
        print(f"❌ Error general obteniendo descripciones semánticas: {e}")
        return {}
    finally:
        if should_close and conn:
            conn.close()

def identify_dataset_with_llm(query: str, available_datasets: dict, semantic_descriptions: dict, user_context: dict) -> str:
    """
    Usa LLM para seleccionar el dataset más apropiado basándose en descripciones semánticas.
    Retorna None si no encuentra un dataset válido en lugar de usar fallback.
    """
    if not available_datasets:
        print("⚠️ No hay datasets disponibles")
        return None
    
    # Construir lista de datasets con sus descripciones
    datasets_info = []
    table_name_mapping = {}  # Mapeo de nombre amigable → nombre real
    
    for table_name, info in available_datasets.items():
        semantic_desc = semantic_descriptions.get(table_name, info.get("description", "Sin descripción"))
        
        # Manejar main_columns que pueden contener None
        main_columns = info.get('main_columns', [])[:5]
        valid_columns = [col for col in main_columns if col is not None and col != ""]
        columns_str = ', '.join(valid_columns) if valid_columns else "N/A"
        
        # Obtener nombre amigable (sin sufijo)
        friendly_name = info.get('friendly_name', table_name)
        
        # Guardar mapeo
        table_name_mapping[friendly_name.lower()] = table_name
        table_name_mapping[table_name.lower()] = table_name  # También mapear el nombre completo
        
        datasets_info.append(f"""
                                Dataset ID: {table_name}
                                Descripción: {semantic_desc}
                                Columnas principales: {columns_str}
                                Cantidad de filas: {info.get('row_count', 'N/A')}
                            """)
    
    # Considerar historial del usuario
    common_datasets_info = ""
    if user_context.get("common_datasets"):
        common_datasets = user_context['common_datasets'][:3]
        valid_common = [ds for ds in common_datasets if ds is not None and ds != ""]
        if valid_common:
            common_datasets_info = f"\nDATASETS MÁS USADOS POR EL USUARIO: {', '.join(valid_common)}"
    
    prompt = f"""
        Analiza la consulta del usuario y selecciona el dataset MÁS apropiado.

        CONSULTA DEL USUARIO:
        {query}
        {common_datasets_info}

        DATASETS DISPONIBLES:
        {chr(10).join(datasets_info)}

        INSTRUCCIONES:
        - Selecciona el dataset cuya descripción mejor coincida con la intención de la consulta
        - Considera el contexto semántico, no solo palabras clave exactas
        - Si el usuario menciona análisis previos, considera los datasets más usados
        - Si hay ambigüedad, elige el dataset más relevante semánticamente

        IMPORTANTE: Responde SOLO con el Dataset ID completo (ejemplo: crocodile_dataset_303cf324)
        NO uses nombres cortos o amigables. Usa el ID exacto que aparece en "Dataset ID:" arriba.

        Responde SOLO con el Dataset ID, sin explicaciones:
    """
    
    try:
        from nodes import llm_documentHandler
        response = llm_documentHandler.invoke(prompt).content.strip()
        
        # Limpiar respuesta
        selected = response.replace('"', '').replace("'", "").strip().lower()
        
        # Intentar mapear la respuesta al nombre real
        actual_table_name = None
        
        # 1. Verificar si la respuesta es exactamente un nombre de tabla
        if selected in [t.lower() for t in available_datasets.keys()]:
            for table in available_datasets.keys():
                if table.lower() == selected:
                    actual_table_name = table
                    break
        
        # 2. Si no, buscar en el mapeo de nombres amigables
        elif selected in table_name_mapping:
            actual_table_name = table_name_mapping[selected]
        
        # 3. Buscar tablas que empiecen con el nombre dado (fuzzy match)
        else:
            for table in available_datasets.keys():
                if table.lower().startswith(selected):
                    actual_table_name = table
                    break
        
        # No usar fallback, retornar None si no hay coincidencia
        if actual_table_name:
            print(f"🤖 LLM seleccionó dataset: {actual_table_name}")
            if actual_table_name.lower() != selected:
                print(f"   Mapeado desde: {selected}")
            print(f"   Razón: Mejor coincidencia semántica con la consulta")
            return actual_table_name
        else:
            print(f"❌ No se encontró dataset válido para: '{response}'")
            print(f"   Datasets disponibles en BD: {list(available_datasets.keys())}")
            return None  # CAMBIO CRÍTICO: Retornar None en lugar de fallback
            
    except Exception as e:
        print(f"❌ Error en selección con LLM: {e}")
        import traceback
        traceback.print_exc()
        return None

def identify_dataset_from_query(query: str, available_datasets: dict) -> str:
    """
    Identifica qué dataset es más relevante basándose en la consulta del usuario.
    Retorna el nombre de la tabla más apropiada.
    """
    query_lower = query.lower()
    
    # Búsqueda por referencias directas
    for table_name, info in available_datasets.items():
        # Buscar por nombre amigable
        friendly_name = info["friendly_name"].lower()
        if friendly_name in query_lower:
            return table_name
        
        # Buscar por keywords
        for keyword in info["keywords"]:
            if keyword.lower() in query_lower:
                return table_name
    
    # Búsqueda por patrones específicos
    if any(word in query_lower for word in ["viaje", "ride", "booking", "reserva", "transporte"]):
        for table_name in available_datasets:
            if "ride" in table_name or "booking" in table_name:
                return table_name
    
    if any(word in query_lower for word in ["cocodril", "animal", "biolog"]):
        for table_name in available_datasets:
            if "crocodile" in table_name:
                return table_name
    
    # Búsqueda por números (archivo 1, dataset 1, etc.)
    if "archivo 1" in query_lower or "dataset 1" in query_lower or "primer" in query_lower:
        dataset_names = list(available_datasets.keys())
        if dataset_names:
            return dataset_names[0]  # Primer dataset
    
    if "archivo 2" in query_lower or "dataset 2" in query_lower or "segundo" in query_lower:
        dataset_names = list(available_datasets.keys())
        if len(dataset_names) > 1:
            return dataset_names[1]  # Segundo dataset
    
    # Si no se encuentra coincidencia, retornar el primero disponible
    if available_datasets:
        return list(available_datasets.keys())[0]
    
    return None

def identify_dataset_from_query_with_memory(query: str, available_datasets: dict, user_context: dict) -> str:
    """
    Versión mejorada que usa LLM con descripciones semánticas.
    Ahora prioriza selección por LLM usando descripciones semánticas.
    """
    if not available_datasets:
        return None
    
    # Obtener descripciones semánticas de la BD
    semantic_descriptions = get_semantic_descriptions_from_db()
    
    # Si hay descripciones semánticas disponibles, usar LLM para selección inteligente
    if semantic_descriptions:
        print("🧠 Usando LLM para selección de dataset (basado en descripciones semánticas)")
        return identify_dataset_with_llm(query, available_datasets, semantic_descriptions, user_context)
    else:
        print("⚠️ No se encontraron descripciones semánticas, usando método tradicional")
        # Fallback al método original
        base_result = identify_dataset_from_query(query, available_datasets)
        
        # Considerar datasets comunes del usuario
        common_datasets = user_context.get("common_datasets", [])
        if common_datasets and base_result in common_datasets:
            print(f"✅ Dataset confirmado por historial: {base_result}")
            return base_result
        
        # Si hay ambigüedad, preferir el dataset más usado históricamente
        if not base_result and common_datasets:
            preferred = common_datasets[0]
            print(f"🔄 Usando dataset preferido por historial: {preferred}")
            return preferred
        
        return base_result