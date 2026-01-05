"""
Модуль инвайтинга пользователей в чаты через Telethon
"""

import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from telethon import TelegramClient
from telethon.tl.functions.messages import AddChatUserRequest
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import InputUser, InputPeerUser, InputPeerChannel, InputPeerChat
from telethon.errors import (
    UserPrivacyRestrictedError,
    UserAlreadyParticipantError,
    ChatAdminRequiredError,
    FloodWaitError,
    ChatNotModifiedError,
    PeerIdInvalidError,
    UsernameInvalidError,
    UsernameNotOccupiedError
)

from .async_manager import AsyncManager
from .database import Database

logger = logging.getLogger(__name__)


class Inviter:
    """Класс для инвайтинга пользователей в чаты"""
    
    def __init__(self, async_manager: AsyncManager, database: Database):
        """
        Инициализация модуля инвайтинга
        
        Args:
            async_manager: Экземпляр AsyncManager для работы с Telegram клиентами
            database: Экземпляр Database для работы с БД
        """
        self.async_manager = async_manager
        self.database = database
        self.stats = {
            'success': 0,
            'error': 0,
            'skipped': 0
        }
        logger.info("Inviter инициализирован")
    
    async def invite_users(
        self,
        phone: str,
        chat_link: str,
        user_list: List[Union[str, int]],
        delay: int = 60
    ) -> Dict[str, int]:
        """
        Инвайтит пользователей в чат
        
        Args:
            phone: Номер телефона аккаунта для инвайта
            chat_link: Ссылка на чат (@username или полная ссылка)
            user_list: Список username или user_id пользователей для инвайта
            delay: Задержка между инвайтами в секундах (по умолчанию 60)
        
        Returns:
            Словарь со статистикой: {success: int, error: int, skipped: int}
        """
        # Сбрасываем статистику
        self.stats = {
            'success': 0,
            'error': 0,
            'skipped': 0
        }
        
        client = None
        try:
            # Получаем account_id по phone
            account_data = self.async_manager.account_manager.get_account_by_phone(phone)
            if not account_data:
                logger.error(f"Аккаунт не найден: {phone}")
                return self.stats
            
            account_id = account_data['id']
            
            # Создаём клиента
            client = self.async_manager.create_client(phone)
            if not client:
                logger.error(f"Не удалось создать клиента для {phone}")
                return self.stats
            
            # Подключаемся и авторизуемся
            await client.connect()
            if not await client.is_user_authorized():
                logger.error(f"Клиент не авторизован для {phone}")
                await self.async_manager.disconnect(client)
                return self.stats
            
            # Получаем информацию о чате
            chat_entity = await self._get_chat_entity(client, chat_link)
            if not chat_entity:
                logger.error(f"Не удалось получить информацию о чате: {chat_link}")
                await self.async_manager.disconnect(client)
                return self.stats
            
            chat_id = chat_entity.id
            is_channel = hasattr(chat_entity, 'broadcast') and chat_entity.broadcast
            
            logger.info(f"Начинаем инвайт пользователей в чат {chat_link} (ID: {chat_id})")
            logger.info(f"Всего пользователей для инвайта: {len(user_list)}")
            
            # Инвайтим каждого пользователя
            total_users = len(user_list)
            for index, user_identifier in enumerate(user_list, 1):
                try:
                    # Получаем user_id из username или используем переданный ID
                    user_id = await self._get_user_id(client, user_identifier)
                    if not user_id:
                        logger.warning(f"Не удалось получить user_id для: {user_identifier}")
                        self.stats['skipped'] += 1
                        continue
                    
                    # Пытаемся добавить пользователя
                    result = await self._invite_user(
                        client=client,
                        chat_entity=chat_entity,
                        user_id=user_id,
                        is_channel=is_channel
                    )
                    
                    # Сохраняем результат в БД
                    invited_at = datetime.now().isoformat()
                    
                    if result['success']:
                        self.stats['success'] += 1
                        status = 'success'
                        logger.info(f"Пользователь @{user_identifier if isinstance(user_identifier, str) else user_id} - успешно добавлен")
                    elif result['skipped']:
                        self.stats['skipped'] += 1
                        status = f"skipped: {result['reason']}"
                        logger.info(f"Пользователь @{user_identifier if isinstance(user_identifier, str) else user_id} - пропущен: {result['reason']}")
                    else:
                        self.stats['error'] += 1
                        status = f"error: {result['error']}"
                        logger.error(f"Ошибка инвайта пользователя @{user_identifier if isinstance(user_identifier, str) else user_id}: {result['error']}")
                    
                    # Сохраняем в БД
                    query = """
                        INSERT INTO invites (account_id, user_id, chat_id, status, invited_at)
                        VALUES (?, ?, ?, ?, ?)
                    """
                    self.database.execute(
                        query,
                        (account_id, user_id, chat_id, status, invited_at)
                    )
                    
                    # Логируем прогресс
                    logger.info(f"Прогресс: Инвайтено {index}/{total_users} (Успешно: {self.stats['success']}, Ошибок: {self.stats['error']}, Пропущено: {self.stats['skipped']})")
                    
                    # Задержка между инвайтами (кроме последнего)
                    if index < total_users:
                        await asyncio.sleep(delay)
                        
                except Exception as e:
                    logger.error(f"Неожиданная ошибка при инвайте пользователя {user_identifier}: {e}", exc_info=True)
                    self.stats['error'] += 1
                    
                    # Сохраняем ошибку в БД
                    try:
                        user_id = await self._get_user_id(client, user_identifier) if isinstance(user_identifier, str) else user_identifier
                        invited_at = datetime.now().isoformat()
                        status = f"error: {str(e)}"
                        query = """
                            INSERT INTO invites (account_id, user_id, chat_id, status, invited_at)
                            VALUES (?, ?, ?, ?, ?)
                        """
                        self.database.execute(
                            query,
                            (account_id, user_id, chat_id, status, invited_at)
                        )
                    except Exception as db_error:
                        logger.error(f"Ошибка сохранения в БД: {db_error}")
            
            logger.info(f"Инвайт завершён. Статистика: {self.stats}")
            return self.stats
            
        except Exception as e:
            logger.error(f"Критическая ошибка при инвайте пользователей: {e}", exc_info=True)
            return self.stats
            
        finally:
            # Отключаемся от клиента
            if client:
                await self.async_manager.disconnect(client)
    
    async def _get_chat_entity(self, client: TelegramClient, chat_link: str):
        """
        Получает сущность чата по ссылке
        
        Args:
            client: TelegramClient
            chat_link: Ссылка на чат (@username или полная ссылка)
        
        Returns:
            Chat или Channel объект или None при ошибке
        """
        try:
            # Убираем @ если есть и извлекаем username
            username = chat_link.replace('@', '').replace('https://t.me/', '').replace('http://t.me/', '').strip()
            
            # Получаем сущность чата
            entity = await client.get_entity(username)
            return entity
            
        except (UsernameInvalidError, UsernameNotOccupiedError) as e:
            logger.error(f"Неверный username чата: {chat_link} - {e}")
            return None
        except PeerIdInvalidError as e:
            logger.error(f"Неверный ID чата: {chat_link} - {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка получения информации о чате {chat_link}: {e}", exc_info=True)
            return None
    
    async def _get_user_id(self, client: TelegramClient, user_identifier: Union[str, int]) -> Optional[int]:
        """
        Получает user_id из username или возвращает переданный ID
        
        Args:
            client: TelegramClient
            user_identifier: Username (str) или user_id (int)
        
        Returns:
            user_id или None при ошибке
        """
        try:
            # Если это уже число, возвращаем его
            if isinstance(user_identifier, int):
                return user_identifier
            
            # Если это строка, пытаемся получить user_id
            if isinstance(user_identifier, str):
                # Убираем @ если есть
                username = user_identifier.replace('@', '').strip()
                
                # Получаем информацию о пользователе
                entity = await client.get_entity(username)
                return entity.id
            
            return None
            
        except (UsernameInvalidError, UsernameNotOccupiedError) as e:
            logger.warning(f"Неверный username пользователя: {user_identifier} - {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка получения user_id для {user_identifier}: {e}", exc_info=True)
            return None
    
    async def _invite_user(
        self,
        client: TelegramClient,
        chat_entity: Any,
        user_id: int,
        is_channel: bool
    ) -> Dict[str, Any]:
        """
        Добавляет пользователя в чат
        
        Args:
            client: TelegramClient
            chat_entity: Сущность чата (Chat или Channel)
            user_id: ID пользователя для добавления
            is_channel: True если это канал, False если группа
        
        Returns:
            Словарь с результатом: {success: bool, skipped: bool, reason: str, error: str}
        """
        # Получаем InputPeer для пользователя (выносим за try для использования в FloodWaitError)
        try:
            user_entity = await client.get_entity(user_id)
            input_user = await client.get_input_entity(user_entity)
        except Exception as e:
            error_msg = f'Ошибка получения информации о пользователе {user_id}: {str(e)}'
            logger.error(error_msg)
            return {
                'success': False,
                'skipped': False,
                'reason': '',
                'error': error_msg
            }
        
        try:
            # Выбираем метод в зависимости от типа чата
            if is_channel:
                # Для каналов используем InviteToChannelRequest
                await client(InviteToChannelRequest(
                    channel=chat_entity,
                    users=[input_user]
                ))
            else:
                # Для групп используем AddChatUserRequest
                await client(AddChatUserRequest(
                    chat_id=chat_entity.id,
                    user_id=input_user,
                    fwd_limit=10
                ))
            
            return {'success': True, 'skipped': False, 'reason': '', 'error': ''}
            
        except UserPrivacyRestrictedError:
            # Пользователь ограничил приватность - пропускаем
            return {
                'success': False,
                'skipped': True,
                'reason': 'UserPrivacyRestrictedError - пользователь ограничил приватность',
                'error': ''
            }
        
        except UserAlreadyParticipantError:
            # Пользователь уже в чате - пропускаем
            return {
                'success': False,
                'skipped': True,
                'reason': 'UserAlreadyParticipantError - пользователь уже в чате',
                'error': ''
            }
        
        except ChatAdminRequiredError as e:
            # Требуются права администратора - логируем ошибку
            error_msg = f'ChatAdminRequiredError - требуются права администратора: {str(e)}'
            logger.error(error_msg)
            return {
                'success': False,
                'skipped': False,
                'reason': '',
                'error': error_msg
            }
        
        except FloodWaitError as e:
            # FloodWait - пауза и повтор
            wait_time = e.seconds
            logger.warning(f"FloodWaitError: нужно подождать {wait_time} секунд")
            await asyncio.sleep(wait_time)
            
            # Повторяем попытку
            try:
                if is_channel:
                    await client(InviteToChannelRequest(
                        channel=chat_entity,
                        users=[input_user]
                    ))
                else:
                    await client(AddChatUserRequest(
                        chat_id=chat_entity.id,
                        user_id=input_user,
                        fwd_limit=10
                    ))
                
                return {'success': True, 'skipped': False, 'reason': '', 'error': ''}
            except Exception as retry_error:
                error_msg = f'Ошибка после FloodWait: {str(retry_error)}'
                logger.error(error_msg)
                return {
                    'success': False,
                    'skipped': False,
                    'reason': '',
                    'error': error_msg
                }
        
        except ChatNotModifiedError as e:
            # Чат не изменён - логируем
            error_msg = f'ChatNotModifiedError - {str(e)}'
            logger.warning(error_msg)
            return {
                'success': False,
                'skipped': True,
                'reason': error_msg,
                'error': ''
            }
        
        except PeerIdInvalidError as e:
            # Неверный ID - логируем
            error_msg = f'PeerIdInvalidError - неверный ID: {str(e)}'
            logger.error(error_msg)
            return {
                'success': False,
                'skipped': False,
                'reason': '',
                'error': error_msg
            }
        
        except Exception as e:
            # Остальные ошибки - логируем с полным описанием
            error_msg = f'{type(e).__name__} - {str(e)}'
            logger.error(f"Неожиданная ошибка при инвайте пользователя {user_id}: {error_msg}", exc_info=True)
            return {
                'success': False,
                'skipped': False,
                'reason': '',
                'error': error_msg
            }
    
    def get_invite_stats(self) -> Dict[str, int]:
        """
        Возвращает статистику инвайтов
        
        Returns:
            Словарь со статистикой: {success: int, error: int, skipped: int}
        """
        return self.stats.copy()

