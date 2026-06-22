import uuid

from config import SINGLE_USER_ID
from database import get_connection
from services.cloudinary_service import delete_chat_folder_from_cloudinary

def is_chat_active(chat_id: str) -> bool:
    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT 1
                FROM chats
                WHERE id = %s
                AND is_deleted = FALSE
            """, (chat_id,))

            return cur.fetchone() is not None

    finally:
        conn.close()

def create_chat(name: str):
    """
    Crea un nuevo chat.
    """

    chat_id = str(uuid.uuid4())

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute("""
                INSERT INTO chats (
                    id,
                    name
                )
                VALUES (
                    %s,
                    %s
                )
                RETURNING
                    id,
                    name,
                    created_at,
                    updated_at
            """, (chat_id, name))

            row = cur.fetchone()

            conn.commit()

            return {
                "id": str(row[0]),
                "name": row[1],
                "created_at": row[2],
                "updated_at": row[3]
            }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        conn.close()


def get_chats():
    """
    Obtiene todos los chats no eliminados.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT
                    id,
                    name,
                    created_at,
                    updated_at
                FROM chats
                WHERE is_deleted = FALSE
                ORDER BY updated_at DESC
            """)

            rows = cur.fetchall()

            return [
                {
                    "id": str(row[0]),
                    "name": row[1],
                    "created_at": row[2],
                    "updated_at": row[3]
                }
                for row in rows
            ]

    finally:
        conn.close()


def update_chat_name(chat_id: str, name: str):
    """
    Renombra un chat.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute("""
                UPDATE chats
                SET
                    name = %s,
                    updated_at = NOW()
                WHERE
                    id = %s
                    AND is_deleted = FALSE
                RETURNING
                    id,
                    name,
                    created_at,
                    updated_at
            """, (name, chat_id))

            row = cur.fetchone()

            conn.commit()

            if not row:
                return None

            return {
                "id": str(row[0]),
                "name": row[1],
                "created_at": row[2],
                "updated_at": row[3]
            }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        conn.close()

def delete_chat(chat_id: str):
    conn = get_connection()

    try:
        with conn.cursor() as cur:

            # 1. validar que el chat existe y no esté borrado
            cur.execute("""
                SELECT id
                FROM chats
                WHERE id = %s AND is_deleted = FALSE
            """, (chat_id,))

            chat = cur.fetchone()

            if not chat:
                return False

            thread_id = chat[0]

            # 2. borrar assets en Cloudinary
            delete_chat_folder_from_cloudinary(
                SINGLE_USER_ID,
                thread_id
            )

            # 3. borrado lógico en DB
            cur.execute("""
                UPDATE chats
                SET is_deleted = TRUE,
                    updated_at = NOW()
                WHERE id = %s
            """, (chat_id,))

            conn.commit()

            return True

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        conn.close()