import cloudinary
import cloudinary.uploader
import os

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

def upload_plot_to_cloudinary(filepath: str) -> dict | None:
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
            folder="plots"
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