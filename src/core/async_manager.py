"""
Менеджер асинхронных операций с Telegram через Telethon
"""

import logging
import asyncio
from typing import Optional, Dict, Any, Callable
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    FloodWaitError,
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    ApiIdInvalidError,
    PhoneCodeExpiredError
)

from .account_manager import AccountManager
from .database import Database

logger = logging.getLogger(__name__)


class AsyncManager:
    """Менеджер для асинхронных операций с Telegram"""
    
    def __init__(self, account_manager: AccountManager, database: Database):
        """
        Инициализация менеджера асинхронных операций
        
        Args:
            account_manager: Экземпляр AccountManager для работы с аккаунтами
            database: Экземпляр Database для работы с БД
        """
        self.account_manager = account_manager
        self.database = database
        logger.info("AsyncManager инициализирован")
    
    def create_client(self, phone: str) -> Optional[TelegramClient]:
        """
        Создаёт TelegramClient для аккаунта
        
        Args:
            phone: Номер телефона аккаунта
        
        Returns:
            Экземпляр TelegramClient или None, если аккаунт не найден
        
        Raises:
            Exception: При ошибке создания клиента
        """
        try:
            # Получаем данные аккаунта из AccountManager
            account_data = self.account_manager.get_account_by_phone(phone)
            
            if not account_data:
                logger.error(f"Аккаунт не найден: {phone}")
                return None
            
            # Создаём сессию
            session = None
            if account_data.get('session_string'):
                try:
                    session = StringSession(account_data['session_string'])
                    logger.debug(f"Сессия восстановлена из строки для {phone}")
                except Exception as e:
                    logger.warning(f"Не удалось восстановить сессию для {phone}: {e}")
                    session = None
            
            # Если сессии нет, создаём новую
            if session is None:
                # Используем временную сессию в памяти
                session = StringSession()
                logger.debug(f"Создана новая сессия для {phone}")
            
            # Создаём TelegramClient
            client = TelegramClient(
                session,
                account_data['api_id'],
                account_data['api_hash']
            )
            
            logger.info(f"TelegramClient создан для аккаунта: {phone}")
            return client
            
        except Exception as e:
            logger.error(f"Ошибка создания TelegramClient для {phone}: {e}", exc_info=True)
            raise
    
    async def start_client(
        self,
        client: TelegramClient,
        phone: str,
        code_callback: Optional[Callable[[str], str]] = None,
        password_callback: Optional[Callable[[str], str]] = None
    ) -> bool:
        """
        Авторизует клиента в Telegram
        
        Args:
            client: Экземпляр TelegramClient
            phone: Номер телефона
            code_callback: Функция для получения кода подтверждения (phone) -> code
        
        Returns:
            True если авторизация успешна, False в противном случае
        
        Raises:
            Exception: При ошибке авторизации
        """
        try:
            # Запускаем клиента
            await client.connect()
            
            if not await client.is_user_authorized():
                logger.info(f"Клиент не авторизован, начинаем авторизацию для {phone}")
                
                # Отправляем запрос на код
                try:
                    await client.send_code_request(phone)
                    logger.info(f"Запрос кода отправлен для {phone}")
                except PhoneNumberInvalidError:
                    logger.error(f"Невалидный номер телефона: {phone}")
                    return False
                except FloodWaitError as e:
                    logger.error(f"FloodWait для {phone}: нужно подождать {e.seconds} секунд")
                    await asyncio.sleep(e.seconds)
                    # Повторяем попытку
                    await client.send_code_request(phone)
                
                # Получаем код через callback
                if code_callback:
                    code = code_callback(phone)
                else:
                    # Если callback не предоставлен, запрашиваем через input (для тестирования)
                    code = input(f"Введите код для {phone}: ")
                
                if not code:
                    logger.error(f"Код не предоставлен для {phone}")
                    return False
                
                # Пытаемся войти с кодом
                try:
                    await client.sign_in(phone, code)
                    logger.info(f"Успешная авторизация для {phone}")
                    
                    # Сохраняем сессию в БД
                    session_string = client.session.save()
                    self._save_session_string(phone, session_string)
                    
                    return True
                    
                except SessionPasswordNeededError:
                    logger.warning(f"Требуется пароль 2FA для {phone}")
                    
                    # Запрашиваем пароль через callback
                    if password_callback:
                        password = password_callback(phone)
                        if password:
                            try:
                                await client.sign_in(password=password)
                                logger.info(f"Успешная авторизация с паролем 2FA для {phone}")
                                
                                # Сохраняем сессию в БД
                                session_string = client.session.save()
                                self._save_session_string(phone, session_string)
                                
                                return True
                            except Exception as e:
                                logger.error(f"Ошибка авторизации с паролем 2FA для {phone}: {e}", exc_info=True)
                                return False
                        else:
                            logger.error(f"Пароль 2FA не предоставлен для {phone}")
                            return False
                    else:
                        logger.error(f"Требуется пароль 2FA, но password_callback не предоставлен для {phone}")
                        return False
                    
                except PhoneCodeInvalidError:
                    logger.error(f"Неверный код для {phone}")
                    return False
                    
                except PhoneCodeExpiredError:
                    logger.error(f"Код истёк для {phone}")
                    return False
                    
            else:
                logger.info(f"Клиент уже авторизован для {phone}")
                return True
                
        except FloodWaitError as e:
            logger.error(f"FloodWait при авторизации {phone}: нужно подождать {e.seconds} секунд")
            await asyncio.sleep(e.seconds)
            return False
            
        except Exception as e:
            logger.error(f"Ошибка авторизации для {phone}: {e}", exc_info=True)
            return False
    
    async def check_account(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Проверяет аккаунт и получает информацию о пользователе
        
        Args:
            phone: Номер телефона аккаунта
        
        Returns:
            Словарь с данными пользователя или None при ошибке
        """
        client = None
        try:
            # Создаём клиента
            client = self.create_client(phone)
            if not client:
                return None
            
            # Подключаемся
            await client.connect()
            
            # Проверяем авторизацию
            if not await client.is_user_authorized():
                logger.warning(f"Аккаунт {phone} не авторизован")
                await self.disconnect(client)
                return None
            
            # Получаем информацию о себе
            me = await client.get_me()
            
            if not me:
                logger.warning(f"Не удалось получить информацию о пользователе {phone}")
                await self.disconnect(client)
                return None
            
            # Формируем результат
            account_info = {
                'id': me.id,
                'username': me.username,
                'first_name': me.first_name,
                'last_name': me.last_name,
                'phone': me.phone,
                'is_bot': me.bot,
                'is_premium': getattr(me, 'premium', False)
            }
            
            logger.info(f"Информация о аккаунте {phone} получена: {account_info}")
            return account_info
            
        except FloodWaitError as e:
            logger.error(f"FloodWait при проверке {phone}: нужно подождать {e.seconds} секунд")
            await asyncio.sleep(e.seconds)
            return None
            
        except Exception as e:
            logger.error(f"Ошибка проверки аккаунта {phone}: {e}", exc_info=True)
            return None
            
        finally:
            # Отключаемся в любом случае
            if client:
                await self.disconnect(client)
    
    async def disconnect(self, client: TelegramClient) -> None:
        """
        Отключает клиента от Telegram
        
        Args:
            client: Экземпляр TelegramClient для отключения
        """
        try:
            if client.is_connected():
                await client.disconnect()
                logger.info("Клиент отключён")
            else:
                logger.debug("Клиент уже отключён")
        except Exception as e:
            logger.error(f"Ошибка отключения клиента: {e}", exc_info=True)
    
    def _save_session_string(self, phone: str, session_string: str) -> None:
        """
        Сохраняет строку сессии в базу данных
        
        Args:
            phone: Номер телефона аккаунта
            session_string: Строка сессии для сохранения
        """
        try:
            query = "UPDATE accounts SET session_string = ? WHERE phone = ?"
            self.database.execute(query, (session_string, phone))
            logger.info(f"Сессия сохранена для аккаунта {phone}")
        except Exception as e:
            logger.error(f"Ошибка сохранения сессии для {phone}: {e}", exc_info=True)

