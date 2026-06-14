import uuid

from database import get_connection


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
    """
    Borrado lógico del chat.
    """

    conn = get_connection()

    try:
        with conn.cursor() as cur:

            cur.execute("""
                UPDATE chats
                SET
                    is_deleted = TRUE,
                    updated_at = NOW()
                WHERE
                    id = %s
                    AND is_deleted = FALSE
            """, (chat_id,))

            conn.commit()

            return cur.rowcount > 0

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        conn.close()