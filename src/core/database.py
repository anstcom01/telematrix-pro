"""
Менеджер SQLite базы данных для TeleMatrix Pro
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Tuple, Any

logger = logging.getLogger(__name__)


class Database:
    """Менеджер базы данных SQLite"""
    
    def __init__(self, db_path: str = "telematrix.db"):
        """
        Инициализация менеджера базы данных
        
        Args:
            db_path: Путь к файлу базы данных (по умолчанию telematrix.db в корне проекта)
        """
        # Преобразуем путь в абсолютный, если указан относительный
        if not Path(db_path).is_absolute():
            # Путь относительно корня проекта
            project_root = Path(__file__).parent.parent.parent
            db_path = project_root / db_path
        
        self.db_path = str(db_path)
        self.connection: Optional[sqlite3.Connection] = None
        logger.info(f"Инициализация базы данных: {self.db_path}")
    
    def connect(self) -> None:
        """Создаёт подключение к базе данных"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
            logger.info("Подключение к базе данных установлено")
        except sqlite3.Error as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            raise
    
    def create_tables(self) -> None:
        """Создаёт все необходимые таблицы в базе данных"""
        if not self.connection:
            self.connect()
        
        tables = [
            """CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                api_id INTEGER NOT NULL,
                api_hash TEXT NOT NULL,
                session_string TEXT,
                created_at TEXT NOT NULL
            )""",
            
            """CREATE TABLE IF NOT EXISTS proxy_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL UNIQUE,
                proxy_type TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                username TEXT,
                password TEXT,
                rotation_enabled INTEGER DEFAULT 0,
                rotation_interval INTEGER DEFAULT 0,
                last_used TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS parsed_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                chat_id INTEGER,
                parsed_at TEXT NOT NULL
            )""",
            
            """CREATE TABLE IF NOT EXISTS invites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                invited_at TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_text TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                action TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )"""
        ]
        
        try:
            cursor = self.connection.cursor()
            for table_sql in tables:
                cursor.execute(table_sql)
            self.connection.commit()
            logger.info("Таблицы базы данных созданы успешно")
        except sqlite3.Error as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            if self.connection:
                self.connection.rollback()
            raise
    
    def execute(self, query: str, params: Tuple[Any, ...] = ()) -> Optional[int]:
        """
        Безопасное выполнение SQL запроса
        
        Args:
            query: SQL запрос с параметрами (?, ?)
            params: Кортеж параметров для запроса
        
        Returns:
            ID последней вставленной строки (для INSERT) или None
        """
        if not self.connection:
            self.connect()
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            self.connection.commit()
            logger.debug(f"Запрос выполнен: {query[:50]}...")
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Ошибка выполнения запроса: {e}")
            if self.connection:
                self.connection.rollback()
            raise
    
    def fetch_all(self, query: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
        """
        Получение всех данных по запросу
        
        Args:
            query: SQL запрос с параметрами (?, ?)
            params: Кортеж параметров для запроса
        
        Returns:
            Список строк результата
        """
        if not self.connection:
            self.connect()
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            logger.debug(f"Получено строк: {len(rows)}")
            return rows
        except sqlite3.Error as e:
            logger.error(f"Ошибка получения данных: {e}")
            raise
    
    def close(self) -> None:
        """Закрытие соединения с базой данных"""
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                logger.info("Соединение с базой данных закрыто")
            except sqlite3.Error as e:
                logger.error(f"Ошибка закрытия соединения: {e}")
                raise
    
    def __enter__(self):
        """Поддержка контекстного менеджера (with statement)"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматическое закрытие при выходе из контекста"""
        self.close()

