"""Database schema provisioning for MCP State Server."""

from loguru import logger

from mcp_state_server.database.connection import DatabaseConnection, get_db_connection


class SchemaManager:
    """Manages database schema provisioning and migrations."""

    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize schema manager.

        Args:
            db_connection: Database connection instance
        """
        self.db = db_connection

    def provision_schema(self) -> None:
        """Provision all database tables."""
        logger.info("Provisioning database schema...")
        self._create_conversations_table()
        self._create_messages_table()
        self._create_user_preferences_table()
        self._create_indexes()
        logger.info("Database schema provisioned successfully")

    def _create_conversations_table(self) -> None:
        """Create conversations table."""
        query = """
            CREATE TABLE IF NOT EXISTS conversations (
                id VARCHAR(255) PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                title VARCHAR(500),
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """

        try:
            self.db.execute_query(query, fetch=False)
            logger.info("Conversations table created/verified")
        except Exception as e:
            logger.error(f"Error creating conversations table: {e}")
            raise

    def _create_messages_table(self) -> None:
        """Create messages table."""
        query = """
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                conversation_id VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                tool_calls JSONB,
                tool_call_id VARCHAR(255),
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """

        try:
            self.db.execute_query(query, fetch=False)
            logger.info("Messages table created/verified")
        except Exception as e:
            logger.error(f"Error creating messages table: {e}")
            raise

    def _create_user_preferences_table(self) -> None:
        """Create user preferences table."""
        query = """
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id VARCHAR(255) NOT NULL,
                preference_key VARCHAR(255) NOT NULL,
                preference_value JSONB NOT NULL,
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, preference_key)
            )
        """

        try:
            self.db.execute_query(query, fetch=False)
            logger.info("User preferences table created/verified")
        except Exception as e:
            logger.error(f"Error creating user preferences table: {e}")
            raise

    def _create_indexes(self) -> None:
        """Create database indexes for performance."""
        indexes = [
            ("idx_messages_conversation_id", "messages", "conversation_id"),
            ("idx_messages_created_at", "messages", "created_at"),
            ("idx_conversations_user_id", "conversations", "user_id"),
            ("idx_conversations_updated_at", "conversations", "updated_at"),
        ]

        for index_name, table_name, column_name in indexes:
            # First check if index already exists
            check_query = """
                SELECT EXISTS (
                    SELECT 1 FROM pg_indexes 
                    WHERE schemaname = current_schema() 
                    AND indexname = %s
                )
            """

            try:
                result = self.db.execute_query(check_query, (index_name,))
                index_exists = result[0]["exists"] if result else False

                if index_exists:
                    logger.debug(
                        f"Index {index_name} already exists, skipping creation"
                    )
                    continue

                # Try to create the index
                create_query = (
                    f"CREATE INDEX {index_name} ON {table_name} ({column_name})"
                )
                self.db.execute_query(create_query, fetch=False)
                logger.debug(f"Index {index_name} created successfully")
            except Exception as e:
                error_msg = str(e).lower()
                # Check if it's a permission error or if index already exists
                if "already exists" in error_msg or "duplicate" in error_msg:
                    logger.debug(
                        f"Index {index_name} already exists (detected via error)"
                    )
                elif "must be owner" in error_msg or "permission denied" in error_msg:
                    logger.warning(
                        f"Cannot create index {index_name}: insufficient permissions. "
                        f"Index may need to be created manually by table owner."
                    )
                else:
                    logger.warning(f"Error creating index {index_name}: {e}")


def provision_schema(db_connection: DatabaseConnection | None = None) -> None:
    """
    Provision database schema.

    Args:
        db_connection: Optional database connection. If None, uses global connection.
    """
    if db_connection is None:
        db_connection = get_db_connection()

    schema_manager = SchemaManager(db_connection)
    schema_manager.provision_schema()
