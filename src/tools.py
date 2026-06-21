import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import re
import time
from typing import Any, List, Optional
from langchain_core.tools import Tool
from langchain_experimental.tools import PythonREPLTool
from config import BASE_URL
import dataset_manager
from utils import generate_unique_plot_filename

python_repl = PythonREPLTool()

def auto_rename_plot_files(result: Any) -> Any:
    """
    Automáticamente detecta y renombra archivos de gráficos recién creados
    para agregar timestamp único.
    
    Args:
        result: Resultado de la ejecución de código
    
    Returns:
        Resultado actualizado con el nuevo nombre de archivo
    """
    try:
        outputs_dir = "./src/outputs"
        if not os.path.exists(outputs_dir):
            return result
        
        latest_plot_path = None
        
        # Obtener archivos .png en outputs
        files = [f for f in os.listdir(outputs_dir) if f.endswith('.png')]
        if not files:
            return result
        
        # Buscar archivos recién creados (últimos 5 segundos)
        import time
        current_time = time.time()
        recent_files = []
        
        for filename in files:
            filepath = os.path.join(outputs_dir, filename)
            file_mtime = os.path.getmtime(filepath)
            
            # Si el archivo fue creado/modificado hace menos de 5 segundos
            if current_time - file_mtime < 5:
                recent_files.append((filename, filepath))
        
        # Renombrar archivos sin timestamp
        for filename, filepath in recent_files:
            # Verificar si ya tiene timestamp (patrón: _YYYYMMDD_HHMMSS)
            if re.search(r'_\d{8}_\d{6}\.png$', filename):
                latest_plot_path = filepath
                continue  # Ya tiene timestamp, no hacer nada
            
            # Extraer nombre base (sin .png)
            base_name = filename.replace('.png', '')
            
            # Generar nuevo nombre con timestamp
            unique_filename = generate_unique_plot_filename(base_name)
            new_filepath = os.path.join(outputs_dir, unique_filename)
            
            # Renombrar el archivo
            os.rename(filepath, new_filepath)
            latest_plot_path = new_filepath
            print(f"🔄 Archivo renombrado: {filename} → {unique_filename}")
            
            # Actualizar el resultado si menciona el archivo antiguo
            if result and isinstance(result, str):
                result = result.replace(filename, unique_filename)
        
        print(
            "AUTO_RENAME latest_plot_path:",
            latest_plot_path
        )
        
        return {
            "result": result,
            "plot_path": latest_plot_path
        }
        
    except Exception as e:
        print(f"⚠️ Error al renombrar archivos: {e}")
        return result
    
def sanitize_plot_code(code: str) -> str:
    """
    Elimina plt.show() y agrega guardado automático de gráficos.
    """
    from datetime import datetime
    
    # Eliminar plt.show()
    code = re.sub(r'plt\.show\(\s*\)', '', code)
    
    # Si el código contiene plt.plot, plt.bar, df.plot, etc. y NO tiene plt.savefig
    has_plotting = any(pattern in code for pattern in ['plt.', 'df.plot', 'sns.'])
    has_savefig = 'plt.savefig' in code
    
    if has_plotting and not has_savefig:
        # Agregar guardado automático al final
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        save_code = f"""
# Auto-guardado de gráfico
output_path = "src/outputs/grafico_{timestamp}.png"
plt.savefig(output_path, bbox_inches='tight', dpi=100)
plt.close()
output_path
"""
        code = code + "\n" + save_code
    
    return code

def run_python_with_df(code: str, error_context: Optional[str] = None):
    """
    Ejecuta código Python con acceso al DataFrame `df` ya cargado.
    CAPTURA STDOUT para obtener resultados de print().
    """
    from io import StringIO
    import sys
    
    # Verificar que hay un dataset cargado
    if dataset_manager.df is None or not dataset_manager.dataset_loaded:
        return {
            "success": False,
            "result": None,
            "error": "No hay dataset cargado en memoria",
            "error_type": "dataset_not_loaded"
        }
    
    code = sanitize_plot_code(code)

    # Contexto completo de ejecución
    local_vars = {
        "df": dataset_manager.df, 
        "pd": pd, 
        "plt": plt, 
        "sns": sns, 
        "os": os,
        "np": pd.np if hasattr(pd, 'np') else None
    }
    
    global_vars = {
        "df": dataset_manager.df,
        "pd": pd,
        "plt": plt,
        "sns": sns,
        "os": os
    }

    prohibited_patterns = [
        "pd.DataFrame(",
        "pandas.DataFrame(",
        "DataFrame(",
        "= pd.read_csv",
        "= pd.read_excel",
        "# Datos de ejemplo",
        "datos de ejemplo",
        "reemplaza con tu DataFrame"
    ]
    
    # Validar patrones prohibidos
    for pattern in prohibited_patterns:
        if pattern in ["pd.DataFrame(", "pandas.DataFrame(", "DataFrame("]:
            if re.search(r'(pd\.|pandas\.)?DataFrame\s*\(', code):
                return {
                    "success": False,
                    "result": None,
                    "error": f"Código bloqueado. Detectado intento de crear DataFrame. Usa SOLO el df existente.",
                    "error_type": "prohibited_pattern"
                }
        elif pattern.lower() in code.lower():
            return {
                "success": False,
                "result": None,
                "error": f"Código bloqueado. Detectado patrón prohibido: '{pattern}'",
                "error_type": "prohibited_pattern"
            }

    # CAPTURAR STDOUT
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    
    try:
        import ast
        result = None
        
        parsed = ast.parse(code)
        if parsed.body and isinstance(parsed.body[-1], ast.Expr):
            # Ejecutar todo excepto la última expresión
            last_expr = parsed.body.pop()
            exec(compile(ast.Module(parsed.body, type_ignores=[]), filename="<ast>", mode="exec"), global_vars, local_vars)
            # Evaluar la última expresión
            result = eval(compile(ast.Expression(last_expr.value), filename="<ast>", mode="eval"), global_vars, local_vars)
        else:
            # Ejecutar todo el código
            exec(code, global_vars, local_vars)
            result = None

        # Obtener el output capturado
        stdout_output = captured_output.getvalue()

        # Restaurar stdout
        sys.stdout = old_stdout

        # Renombrar archivos de gráficos generados
        plot_info = auto_rename_plot_files(result)

        result = plot_info["result"]

        plot_path = plot_info["plot_path"]

        # Subir gráfico a cloudinary
        generated_plot = None

        if plot_path:

            from src.services.cloudinary_service import (
                upload_plot_to_cloudinary
            )

            cloudinary_result = (
                upload_plot_to_cloudinary(
                    plot_path
                )
            )

            generated_plot = {
                "filename": os.path.basename(plot_path),

                "local_path": plot_path,

                "local_url":
                    f"{BASE_URL}/outputs/{os.path.basename(plot_path)}",

                "cloudinary_url":
                    (
                        cloudinary_result["url"]
                        if cloudinary_result
                        else None
                    ),

                "cloudinary_public_id":
                    (
                        cloudinary_result["public_id"]
                        if cloudinary_result
                        else None
                    )
            }

        # Determinar el resultado final con validación segura
        final_result = None

        # Verificar stdout de forma segura
        if isinstance(stdout_output, str) and len(stdout_output.strip()) > 0:
            final_result = stdout_output.strip()
        elif result is not None:
            # Si result es un objeto de pandas, convertirlo a string
            try:
                if hasattr(result, 'to_string'):
                    final_result = result.to_string()
                elif hasattr(result, 'tolist'):
                    final_result = str(result.tolist())
                else:
                    final_result = str(result)
            except:
                final_result = str(result)
        else:
            final_result = "✅ Código ejecutado con éxito."

        # Prints de prueba, ELIMINAR
        # print("generated_plot:", generated_plot)
        # print("plot_path:", plot_path)
        # print("cloudinary_result:", cloudinary_result if plot_path else None)

        return {
            "success": True,
            "result": final_result,
            "error": None,
            "error_type": None,
            "generated_plot": generated_plot
        }
        
    except Exception as e:
        # Restaurar stdout en caso de error
        sys.stdout = old_stdout
        
        error_type = type(e).__name__
        return {
            "success": False,
            "result": None,
            "error": str(e),
            "error_type": error_type
        }

def get_tools_summary(tools: List[Tool]) -> str:
    """Devuelve un resumen con nombre y descripción de cada tool."""
    return "\n".join([f"- {t.name}: {t.description}" for t in tools])

# Funciones de herramientas de datos
def get_dataframe(_):
    """
    Devuelve el DataFrame completo al LLM.
    Este tool permite que el agente acceda a 'df' directamente para cualquier análisis.
    """

    # Verificar que hay dataset cargado
    if dataset_manager.df is None or not dataset_manager.dataset_loaded:
        return "Error: No hay dataset cargado. Use ensure_dataset_loaded primero."

    # Verificar que hay dataset cargado (NO recargar)
    if dataset_manager.df is None or not dataset_manager.dataset_loaded:
        return "Error: No hay dataset cargado en memoria"
    
    return dataset_manager.df

def get_summary(_):
    """Devuelve un resumen general del dataset"""
    return str(dataset_manager.df.describe(include="all"))

def get_columns(_):
    """Devuelve las columnas del dataset"""
    return str(dataset_manager.df.columns.tolist())

def get_missing_values(_):
    """Devuelve la cantidad de valores nulos por columna"""
    return str(dataset_manager.df.isnull().sum())

def get_dtypes_and_uniques(_):
    """Devuelve los tipos de datos de cada columna y la cantidad de valores únicos."""
    return str(pd.DataFrame({
        "dtype": dataset_manager.df.dtypes,
        "unique_values": dataset_manager.df.nunique()
}))

def get_categorical_distribution(column: str):
    """Devuelve la distribución de frecuencias de una columna categórica."""
    if column not in dataset_manager.df.columns:
        return f"Columna {column} no encontrada."
    return str(dataset_manager.df[column].value_counts(dropna=False).head(20))

def get_numeric_dispersion(_):
    """Devuelve rango, varianza y desviación estándar de variables numéricas."""
    numeric_cols = dataset_manager.df.select_dtypes(include=["number"])
    return str(numeric_cols.agg(["min", "max", "var", "std"]))

def get_correlations(_):
    """Devuelve la matriz de correlaciones entre variables numéricas."""
    numeric_cols = dataset_manager.df.select_dtypes(include=["number"])
    return str(numeric_cols.corr())

def detect_outliers(column: str):
    """Devuelve los valores atípicos (según IQR) de una columna numérica."""
    if column not in dataset_manager.df.columns:
        return f"Columna {column} no encontrada."
    if not pd.api.types.is_numeric_dtype(dataset_manager.df[column]):
        return f"La columna {column} no es numérica."
    Q1 = dataset_manager.df[column].quantile(0.25)
    Q3 = dataset_manager.df[column].quantile(0.75)
    IQR = Q3 - Q1
    outliers = dataset_manager.df[(dataset_manager.df[column] < Q1 - 1.5 * IQR) | (dataset_manager.df[column] > Q3 + 1.5 * IQR)][column]
    return str(outliers.head(50))  # solo mostramos algunos

def get_time_series_summary(_):
    """Devuelve la cantidad de viajes por fecha (si existe columna de fecha)."""
    if "Date" not in dataset_manager.df.columns:
        return "No existe columna Date."
    dataset_manager.df["Date"] = pd.to_datetime(dataset_manager.df["Date"], errors="coerce")
    return str(dataset_manager.df.groupby(dataset_manager.df["Date"].dt.date).size().head(30))

# Funciones de visualización
def plot_histogram(column: str):
    """Genera un histograma de una columna numérica, lo guarda en carpeta y lo muestra en ventana."""
    if column not in dataset_manager.df.columns:
        return f"Columna {column} no encontrada."
    if not pd.api.types.is_numeric_dtype(dataset_manager.df[column]):
        return f"La columna {column} no es numérica."
    
    plt.figure(figsize=(10,6))
    dataset_manager.df[column].dropna().hist(bins=30, edgecolor="black", alpha=0.7)
    plt.title(f"Histograma de {column}", fontsize=16)
    plt.xlabel(column, fontsize=12)
    plt.ylabel("Frecuencia", fontsize=12)
    plt.grid(axis="y", alpha=0.5)

    # Usar nombre único con timestamp
    unique_filename = generate_unique_plot_filename(f"histogram_{column}")
    file_path = f"./src/outputs/{unique_filename}"
    plt.savefig(file_path, dpi=300, bbox_inches="tight")
    plt.show()
    return f"✅ Histograma generado y guardado en outputs/{unique_filename}"

def plot_correlation_heatmap(_):
    """Genera un heatmap de correlaciones entre variables numéricas."""
    numeric_cols = dataset_manager.df.select_dtypes(include=["number"])
    if numeric_cols.empty:
        return "No hay columnas numéricas para correlacionar."

    import seaborn as sns
    plt.figure(figsize=(12,8))
    sns.heatmap(numeric_cols.corr(), annot=True, cmap="coolwarm", fmt=".2f")
    plt.title("Mapa de calor de correlaciones", fontsize=16)

    # Usar nombre único con timestamp
    unique_filename = generate_unique_plot_filename("correlation_heatmap")
    file_path = f"./src/outputs/{unique_filename}"
    plt.savefig(file_path, dpi=300, bbox_inches="tight")
    plt.show()
    return f"✅ Heatmap de correlaciones generado y guardado en outputs/{unique_filename}"

def plot_time_series(_):
    """Genera una serie temporal de la cantidad de viajes por día (si existe columna Date)."""
    if "Date" not in dataset_manager.df.columns:
        return "No existe columna Date."
    dataset_manager.df["Date"] = pd.to_datetime(dataset_manager.df["Date"], errors="coerce")
    ts = dataset_manager.df.groupby(dataset_manager.df["Date"].dt.date).size()

    plt.figure(figsize=(14,6))
    ts.plot(kind="line", marker="o", alpha=0.7)
    plt.title("Cantidad de viajes por día", fontsize=16)
    plt.xlabel("Fecha", fontsize=12)
    plt.ylabel("Cantidad de viajes", fontsize=12)
    plt.grid(True, alpha=0.5)

    # Usar nombre único con timestamp
    unique_filename = generate_unique_plot_filename("time_series")
    file_path = f"./src/outputs/{unique_filename}"
    plt.savefig(file_path, dpi=300, bbox_inches="tight")
    plt.show()
    return f"✅ Serie temporal generada y guardada en outputs/{unique_filename}"

def plot_payment_method_distribution(_):
    """Genera un gráfico de barras de los métodos de pago ordenados por frecuencia."""
    if "Payment Method" not in dataset_manager.df.columns:
        return "No existe columna Payment Method."
    
    counts = dataset_manager.df["Payment Method"].value_counts().sort_values(ascending=False)
    
    plt.figure(figsize=(10,6))
    counts.plot(kind="bar", color="skyblue", edgecolor="black")
    plt.title("Métodos de Pago más frecuentes", fontsize=16)
    plt.xlabel("Método de Pago", fontsize=12)
    plt.ylabel("Frecuencia", fontsize=12)
    plt.xticks(rotation=45, ha="right")
    plt.grid(axis="y", alpha=0.5)

    # Usar nombre único con timestamp
    unique_filename = generate_unique_plot_filename("payment_method_distribution")
    file_path = f"./src/outputs/{unique_filename}"
    plt.savefig(file_path, dpi=300, bbox_inches="tight")
    plt.show()
    return f"✅ Gráfico de métodos de pago generado y guardado en outputs/{unique_filename}"

# Lista de herramientas
tools = [
    Tool(name="get_summary", func=get_summary, description="Muestra un resumen estadístico del dataset"),
    Tool(name="get_columns", func=get_columns, description="Muestra las columnas del dataset"),
    Tool(name="get_missing_values", func=get_missing_values, description="Muestra los valores nulos en el dataset"),
    Tool(name="get_dtypes_and_uniques", func=get_dtypes_and_uniques, description="Muestra tipos de datos y cantidad de valores únicos por columna"),
    Tool(name="get_categorical_distribution", func=get_categorical_distribution, description="Muestra distribución de valores en una columna categórica"),
    Tool(name="get_numeric_dispersion", func=get_numeric_dispersion, description="Muestra rango, varianza y desviación estándar de columnas numéricas"),
    Tool(name="get_correlations", func=get_correlations, description="Muestra correlaciones entre variables numéricas"),
    Tool(name="detect_outliers", func=detect_outliers, description="Detecta valores atípicos en una columna numérica"),
    Tool(name="get_time_series_summary", func=get_time_series_summary, description="Muestra cantidad de viajes por fecha"),
    Tool(name="plot_histogram", func=plot_histogram, description="Genera un histograma de una columna numérica"),
    Tool(name="plot_correlation_heatmap", func=plot_correlation_heatmap, description="Genera un heatmap de correlaciones entre variables numéricas"),
    Tool(name="plot_time_series", func=plot_time_series, description="Genera una serie temporal de cantidad de viajes por día"),
    Tool(name="plot_payment_method_distribution", func=plot_payment_method_distribution, description="Genera un gráfico de barras de métodos de pago ordenados por frecuencia"),
    Tool(
        name="Python_Interpreter",
        func=run_python_with_df,
        description="Ejecuta código Python con acceso al DataFrame `df` cargado desde Excel. Usa este df para limpiar datos, convertir columnas y generar gráficos."
    )
]