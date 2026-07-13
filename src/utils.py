import os
import re
import hashlib
import pandas as pd
from datetime import datetime
from dataset_manager import list_stored_tables
from checkpoints import get_postgres_saver, load_conversation_history
from datetime import datetime
from config import SINGLE_USER_THREAD_ID
import math
import numpy as np
import pandas as pd

def clean_data_for_json(data):
    """Función simplificada solo para datasets"""
    if isinstance(data, dict):
        return {k: clean_data_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data_for_json(item) for item in data]
    elif pd.isna(data):
        return "NULL"
    elif hasattr(data, 'isoformat'):  # Timestamps
        return data.isoformat()
    else:
        return data

def clean_state_for_serialization(state):
    """
    Limpia el estado para que sea serializable por msgpack.
    Remueve o convierte objetos no serializables como DataFrames.
    """
    cleaned_state = state.copy()
    
    # Limpiar sql_results si contiene DataFrame
    if "sql_results" in cleaned_state and hasattr(cleaned_state["sql_results"], 'to_dict'):
        df = cleaned_state["sql_results"]
        cleaned_state["sql_results"] = {
            "data": df.head(100).to_dict('records'),  # Limitar a 100 filas
            "columns": df.columns.tolist(),
            "shape": df.shape,
            "serialized": True
        }
    
    # Limpiar otros campos que puedan contener objetos no serializables
    if "df_info" in cleaned_state and "sample" in cleaned_state["df_info"]:
        # Ya está limpio por clean_data_for_json, pero verificar
        pass
    
    # Limpiar execution_history de posibles objetos no serializables
    if "execution_history" in cleaned_state:
        for record in cleaned_state["execution_history"]:
            if "result" in record and hasattr(record["result"], 'to_dict'):
                # Si el resultado es un DataFrame, convertirlo
                record["result"] = f"DataFrame con shape {record['result'].shape}"
    
    return cleaned_state

def show_stored_files():
    """
    Muestra los archivos almacenados en la BD de forma amigable.
    """
    stored_tables = list_stored_tables()
    
    if not stored_tables:
        print("📁 No se encontraron tablas de dataset en la base de datos")
        print("💡 Verifica que las tablas se hayan creado correctamente")
        
        # Mostrar información adicional para debugging
        print("\n🔧 Para verificar manualmente, puedes ejecutar en PostgreSQL:")
        print("   SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        return
    
    print(f"📁 Los siguientes archivos se encuentran en mi BD. Puedes preguntar sobre ellos ({len(stored_tables)} encontrados):")
    for i, table_name in enumerate(stored_tables, 1):
        print(f"   {i}. {table_name}")

def show_conversation_memory(thread_id: str):
    """
    Muestra un resumen de la memoria de conversación para debugging.
    """
    
    conversation_history, user_context = load_conversation_history(thread_id)
    
    if conversation_history:
        print(f"🧠 Memoria encontrada:")
        print(f"   📚 {len(conversation_history)} conversaciones previas")
        print(f"   📊 Datasets usados: {user_context.get('common_datasets', [])}")
        print(f"   🎯 Estrategia preferida: {user_context.get('preferred_analysis_type', 'N/A')}")
        print(f"   ⚠️ Patrones de error: {len(user_context.get('error_patterns', []))}")
        
        # Mostrar última conversación
        if conversation_history:
            last_conv = conversation_history[-1]
            print(f"   🕒 Última consulta: {last_conv.get('query', 'N/A')[:50]}...")
            print(f"   ✅ Fue exitosa: {last_conv.get('success', False)}")
    else:
        print("🧠 No se encontró memoria previa")
    
    print()

def generate_unique_plot_filename(base_name: str) -> str:
    """
    Genera un nombre único para un archivo de gráfico con timestamp.
    
    Args:
        base_name: Nombre base del archivo (ej: "histogram_edad")
    
    Returns:
        Nombre único con timestamp (ej: "histogram_edad_20231008_143022.png")
    """
    # Limpiar el nombre base (remover .png si existe)
    base_name = base_name.replace('.png', '')
    
    # Generar timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Construir nombre único
    unique_name = f"{base_name}_{timestamp}.png"
    
    return unique_name

def extract_text_data(result_text: str):
    """
    Extrae datos estructurados de resultados de texto.
    Detecta listas, diccionarios y otros formatos estructurados.
    """
    import ast
    
    if not result_text or not isinstance(result_text, str):
        return None
    
    try:
        # Limpiar el texto
        text = result_text.strip()
        
        if not text:
            return None
        
        # Intentar parsear como expresión Python literal (listas, dicts, etc.)
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            # Detectar si la línea contiene una lista o diccionario
            if (line.startswith('[') and line.endswith(']')) or \
               (line.startswith('{') and line.endswith('}')):
                try:
                    parsed = ast.literal_eval(line)
                    # Verificar que es un tipo serializable
                    if isinstance(parsed, (list, dict, tuple, str, int, float, bool, type(None))):
                        return parsed
                except (ValueError, SyntaxError):
                    continue
        
        # Si no se encontró formato estructurado, retornar el texto completo
        return {"text": text}
    
    except Exception as e:
        print(f"⚠️ Error extrayendo datos de texto: {e}")
        # Si hay cualquier error, retornar el texto tal cual
        if isinstance(result_text, str):
            return {"text": result_text.strip()}
        return None

def extract_plot_filename_from_result(result_text: str) -> str:
    """
    Extrae el nombre del archivo de gráfico desde el texto de resultado.
    Ahora captura más patrones.
    
    Args:
        result_text: Texto que contiene la ruta del archivo guardado
    
    Returns:
        Nombre del archivo (ej: "histogram_edad_20231008_143022.png") o None
    """
    if not result_text:
        return None
    
    result_str = str(result_text)
    
    # Patrón 1: "outputs/nombre_archivo.png"
    match = re.search(r'outputs[/\\]([^\s\'"]+\.png)', result_str)
    if match:
        return match.group(1)
    
    # Patrón 2: "./src/outputs/nombre_archivo.png"
    match = re.search(r'\.\/src\/outputs[/\\]([^\s\'"]+\.png)', result_str)
    if match:
        return match.group(1)
    
    # Patrón 3: "src/outputs/nombre_archivo.png"
    match = re.search(r'src[/\\]outputs[/\\]([^\s\'"]+\.png)', result_str)
    if match:
        return match.group(1)
    
    # Patrón 4: Solo el nombre del archivo con .png (sin path)
    # Ejemplo: "histogram_booking_value.png" o "`histogram_booking_value.png`"
    match = re.search(r'[`\']?([a-zA-Z0-9_\-]+\.png)[`\']?', result_str)
    if match:
        filename = match.group(1)
        # Verificar que el archivo existe en outputs
        filepath = os.path.join("./src/outputs", filename)
        if os.path.exists(filepath):
            return filename
    
    # Patrón 5: Buscar cualquier .png mencionado
    match = re.search(r'([a-zA-Z0-9_\-]+_\d{8}_\d{6}\.png)', result_str)
    if match:
        return match.group(1)
    
    return None

def get_plot_metadata(filename: str) -> dict:
    """
    Obtiene metadata de un archivo de gráfico.
    
    Args:
        filename: Nombre del archivo (ej: "histogram_edad_20231008_143022.png")
    
    Returns:
        Diccionario con metadata del gráfico
    """
    filepath = os.path.join("./src/outputs", filename)
    
    metadata = {
        "filename": filename,
        "exists": os.path.exists(filepath),
        "created_at": None,
        "size_bytes": None
    }
    
    if metadata["exists"]:
        stat = os.stat(filepath)
        metadata["created_at"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        metadata["size_bytes"] = stat.st_size
    
    return metadata

def calculate_file_hash(file_content: bytes, algorithm: str = 'sha256') -> str:
    """
    Calcula el hash de un archivo basándose en su contenido.
    
    Args:
        file_content: Contenido del archivo en bytes
        algorithm: Algoritmo de hash ('md5', 'sha1', 'sha256')
    
    Returns:
        String con el hash hexadecimal del archivo
    
    Example:
        >>> content = b"Hello World"
        >>> calculate_file_hash(content)
        'a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e'
    """
    if algorithm == 'md5':
        hasher = hashlib.md5()
    elif algorithm == 'sha1':
        hasher = hashlib.sha1()
    elif algorithm == 'sha256':
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"Algoritmo no soportado: {algorithm}")
    
    hasher.update(file_content)
    return hasher.hexdigest()

def verify_file_hash(file_content: bytes, expected_hash: str, algorithm: str = 'sha256') -> bool:
    """
    Verifica si el hash de un archivo coincide con un hash esperado.
    
    Args:
        file_content: Contenido del archivo en bytes
        expected_hash: Hash esperado en formato hexadecimal
        algorithm: Algoritmo de hash usado
    
    Returns:
        True si el hash coincide, False en caso contrario
    """
    calculated_hash = calculate_file_hash(file_content, algorithm)
    return calculated_hash == expected_hash

def is_invalid_result(result, final_result):
    """
    Determina si el resultado obtenido por el código Python debe
    considerarse un fallo lógico (aunque no haya ocurrido una excepción).

    Devuelve:
        (is_invalid: bool, error_message: str)
    """

    # ----------------------------
    # 1. Resultado None
    # ----------------------------
    if result is None:
        text = str(final_result).strip().lower()

        # Si no hubo ningún resultado útil
        if text in [
            "",
            "none",
            "nan",
            "null",
            "numpy.nan",
            "np.nan"
        ]:
            return True, "La consulta no produjo un resultado válido."

        return False, None

    # ----------------------------
    # 2. DataFrame vacío
    # ----------------------------
    if isinstance(result, pd.DataFrame):
        if result.empty:
            return True, "La consulta devolvió un DataFrame vacío."

    # ----------------------------
    # 3. Series vacía
    # ----------------------------
    if isinstance(result, pd.Series):
        if result.empty:
            return True, "La consulta devolvió una Serie vacía."

    # ----------------------------
    # 4. Escalares NaN
    # ----------------------------
    try:
        if pd.isna(result):
            return True, "La consulta devolvió NaN."
    except Exception:
        pass

    # ----------------------------
    # 5. Infinitos
    # ----------------------------
    try:
        if isinstance(result, (float, np.floating)):
            if math.isinf(result):
                return True, "La consulta devolvió un valor infinito."
    except Exception:
        pass

    # ----------------------------
    # 6. Resultado textual
    # ----------------------------
    text = str(final_result).strip().lower()

    invalid_texts = {
        "",
        "none",
        "nan",
        "null",
        "numpy.nan",
        "np.nan",
        "empty dataframe",
        "empty series"
    }

    if text in invalid_texts:
        return True, f"Resultado inválido: {final_result}"

    # ----------------------------
    # Todo OK
    # ----------------------------
    return False, None