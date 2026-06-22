import cloudinary
import cloudinary.uploader
import os

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

def upload_plot_to_cloudinary(filepath: str, user_id: str, thread_id: str) -> dict | None:
    """
    Sube un gráfico a Cloudinary.

    Returns:
        {
            "url": "...",
            "public_id": "...",
            "asset_id": "..."
        }
    """

    try:

        result = cloudinary.uploader.upload(
            filepath,
            folder=f"plots/{user_id}/{thread_id}"
        )

        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "asset_id": result["asset_id"]
        }

    except Exception as e:

        print(
            f"⚠️ Error subiendo a Cloudinary: {e}"
        )

        return None

def delete_chat_folder_from_cloudinary(user_id: str, thread_id: str):
    """
    Elimina todos los assets de un chat en Cloudinary
    usando prefix de carpeta.
    """

    try:
        prefix = f"plots/{user_id}/{thread_id}"

        # 1. Buscar todos los assets dentro del folder
        resources = cloudinary.api.resources(
            type="upload",
            prefix=prefix,
            max_results=500
        )

        public_ids = [r["public_id"] for r in resources.get("resources", [])]

        # 2. Eliminar todos los assets encontrados
        if public_ids:
            cloudinary.uploader.destroy(public_ids, invalidate=True)

        # 3. (opcional) eliminar versiones residuales
        cloudinary.api.delete_resources_by_prefix(prefix)

        return True

    except Exception as e:
        print(f"⚠️ Error borrando carpeta Cloudinary: {e}")
        return False