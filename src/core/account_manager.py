"""
Менеджер Telegram аккаунтов для TeleMatrix Pro
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from telethon import TelegramClient
from telethon.sessions import StringSession

from .database import Database

logger = logging.getLogger(__name__)


class AccountManager:
    """Менеджер для работы с Telegram аккаунтами"""
    
    def __init__(self, database: Database):
        """
        Инициализация менеджера аккаунтов
        
        Args:
            database: Экземпляр Database для работы с БД
        """
        self.db = database
        logger.info("AccountManager инициализирован")
    
    def add_account(
        self,
        phone: str,
        api_id: int,
        api_hash: str,
        session_string: Optional[str] = None
    ) -> int:
        """
        Добавляет аккаунт в базу данных
        
        Args:
            phone: Номер телефона аккаунта
            api_id: API ID из my.telegram.org
            api_hash: API Hash из my.telegram.org
            session_string: Строка сессии Telethon (опционально)
        
        Returns:
            ID созданного аккаунта
        
        Raises:
            Exception: При ошибке добавления аккаунта
        """
        try:
            # Проверяем, не существует ли уже аккаунт с таким номером
            existing = self.get_account_by_phone(phone)
            if existing:
                logger.warning(f"Аккаунт с номером {phone} уже существует")
                raise ValueError(f"Аккаунт с номером {phone} уже существует")
            
            # Создаём запись в БД
            created_at = datetime.now().isoformat()
            query = """
                INSERT INTO accounts (phone, api_id, api_hash, session_string, created_at)
                VALUES (?, ?, ?, ?, ?)
            """
            account_id = self.db.execute(
                query,
                (phone, api_id, api_hash, session_string, created_at)
            )
            
            logger.info(f"Аккаунт добавлен: {phone} (ID: {account_id})")
            return account_id
            
        except Exception as e:
            logger.error(f"Ошибка добавления аккаунта {phone}: {e}")
            raise
    
    def get_all_accounts(self) -> List[Dict[str, Any]]:
        """
        Возвращает список всех аккаунтов
        
        Returns:
            Список словарей с данными аккаунтов
        """
        try:
            query = "SELECT * FROM accounts ORDER BY created_at DESC"
            rows = self.db.fetch_all(query)
            
            accounts = []
            for row in rows:
                accounts.append({
                    'id': row['id'],
                    'phone': row['phone'],
                    'api_id': row['api_id'],
                    'api_hash': row['api_hash'],
                    'session_string': row['session_string'],
                    'created_at': row['created_at']
                })
            
            logger.info(f"Получено аккаунтов: {len(accounts)}")
            return accounts
            
        except Exception as e:
            logger.error(f"Ошибка получения списка аккаунтов: {e}")
            raise
    
    def get_account_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Поиск аккаунта по номеру телефона
        
        Args:
            phone: Номер телефона для поиска
        
        Returns:
            Словарь с данными аккаунта или None, если не найден
        """
        try:
            query = "SELECT * FROM accounts WHERE phone = ? LIMIT 1"
            rows = self.db.fetch_all(query, (phone,))
            
            if rows:
                row = rows[0]
                account = {
                    'id': row['id'],
                    'phone': row['phone'],
                    'api_id': row['api_id'],
                    'api_hash': row['api_hash'],
                    'session_string': row['session_string'],
                    'created_at': row['created_at']
                }
                logger.debug(f"Аккаунт найден: {phone}")
                return account
            
            logger.debug(f"Аккаунт не найден: {phone}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка поиска аккаунта {phone}: {e}")
            raise
    
    def delete_account(self, phone: str) -> bool:
        """
        Удаление аккаунта по номеру телефона
        
        Args:
            phone: Номер телефона аккаунта для удаления
        
        Returns:
            True если аккаунт удалён, False если не найден
        
        Raises:
            Exception: При ошибке удаления
        """
        try:
            # Проверяем существование аккаунта
            account = self.get_account_by_phone(phone)
            if not account:
                logger.warning(f"Аккаунт для удаления не найден: {phone}")
                return False
            
            # Удаляем аккаунт
            query = "DELETE FROM accounts WHERE phone = ?"
            self.db.execute(query, (phone,))
            
            logger.info(f"Аккаунт удалён: {phone}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления аккаунта {phone}: {e}")
            raise
    
    def create_client(self, phone: str) -> Optional[TelegramClient]:
        """
        Создаёт TelegramClient из данных аккаунта
        
        Args:
            phone: Номер телефона аккаунта
        
        Returns:
            Экземпляр TelegramClient или None, если аккаунт не найден
        
        Raises:
            Exception: При ошибке создания клиента
        """
        try:
            # Получаем данные аккаунта
            account = self.get_account_by_phone(phone)
            if not account:
                logger.error(f"Аккаунт не найден: {phone}")
                return None
            
            # Проверяем наличие session_string
            if not account['session_string']:
                logger.error(f"У аккаунта {phone} отсутствует session_string")
                raise ValueError(f"У аккаунта {phone} отсутствует session_string")
            
            # Создаём сессию из строки
            session = StringSession(account['session_string'])
            
            # Создаём клиент
            client = TelegramClient(
                session,
                account['api_id'],
                account['api_hash']
            )
            
            logger.info(f"TelegramClient создан для аккаунта: {phone}")
            return client
            
        except Exception as e:
            logger.error(f"Ошибка создания TelegramClient для {phone}: {e}")
            raise

