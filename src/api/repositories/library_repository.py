from src.database import get_connection


def get_library_datasets():
    """
    Obtiene todos los datasets que poseen al menos
    una visualización generada.
    """

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute("""
                SELECT
                    dataset_id,
                    dataset_name,
                    COUNT(*) AS total_visualizations
                FROM
                    visualizations
                GROUP BY
                    dataset_id,
                    dataset_name
                ORDER BY
                    dataset_name ASC
            """)

            rows = cur.fetchall()

            return [
                {
                    "dataset_id": str(row[0]),
                    "dataset_name": row[1],
                    "total_visualizations": row[2]
                }
                for row in rows
            ]

    finally:

        conn.close()

def get_visualizations_by_dataset(
    dataset_id: str
):
    """
    Devuelve todas las visualizaciones pertenecientes
    a un dataset.
    """

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute("""
                SELECT
                    id,
                    dataset_id,
                    dataset_name,
                    cloudinary_url,
                    cloudinary_public_id,
                    created_at
                FROM
                    visualizations
                WHERE
                    dataset_id = %s
                ORDER BY
                    created_at DESC
            """, (dataset_id,))

            rows = cur.fetchall()

            return [
                {
                    "id": str(row[0]),
                    "dataset_id": str(row[1]),
                    "dataset_name": row[2],
                    "cloudinary_url": row[3],
                    "cloudinary_public_id": row[4],
                    "created_at": row[5]
                }
                for row in rows
            ]

    finally:

        conn.close()

def create_visualization(data):

    db = get_connection()

    query = """
        INSERT INTO visualizations
        (
            user_id,
            chat_id,
            dataset_id,
            dataset_name,
            filename,
            cloudinary_url,
            cloudinary_public_id
        )
        VALUES
        (
            %(user_id)s,
            %(chat_id)s,
            %(dataset_id)s,
            %(dataset_name)s,
            %(filename)s,
            %(cloudinary_url)s,
            %(cloudinary_public_id)s
        )
        RETURNING id;
    """

    result = db.execute(
        query,
        data
    )

    db.commit()

    return result.fetchone()
    