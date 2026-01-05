"""
Модуль парсинга участников из чатов Telegram через Telethon
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from telethon import TelegramClient
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import (
    ChannelParticipantsRecent,
    ChannelParticipantsAdmins,
    ChannelParticipantsBots,
    ChannelParticipantsSearch,
    InputChannel
)
from telethon.errors import (
    FloodWaitError,
    ChatAdminRequiredError,
    UserPrivacyRestrictedError,
    UsernameNotOccupiedError,
    ChannelPrivateError
)

from .async_manager import AsyncManager
from .database import Database

logger = logging.getLogger(__name__)


class Parser:
    """Класс для парсинга участников из чатов Telegram"""
    
    def __init__(self, async_manager: AsyncManager, database: Database):
        """
        Инициализация парсера
        
        Args:
            async_manager: Экземпляр AsyncManager для работы с Telegram
            database: Экземпляр Database для работы с БД
        """
        self.async_manager = async_manager
        self.database = database
        logger.info("Parser инициализирован")
    
    async def parse_chat_participants(
        self,
        phone: str,
        chat_link: str,
        limit: int = 100,
        filters: Optional[Dict[str, bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Парсит участников из чата/канала
        
        Args:
            phone: Номер телефона аккаунта для парсинга
            chat_link: Ссылка на чат (@username или полная ссылка)
            limit: Максимальное количество участников для парсинга
            filters: Словарь с фильтрами:
                - only_usernames: только с @username
                - only_active: только активные (последний вход < 7 дней)
                - exclude_bots: исключить ботов
                - exclude_premium: исключить premium
        
        Returns:
            Список словарей с данными распарсенных участников
        """
        client = None
        parsed_users = []
        
        try:
            # Создаём клиента
            client = self.async_manager.create_client(phone)
            if not client:
                logger.error(f"Не удалось создать клиент для {phone}")
                return []
            
            # Подключаемся
            await client.connect()
            
            # Проверяем авторизацию
            if not await client.is_user_authorized():
                logger.error(f"Аккаунт {phone} не авторизован")
                return []
            
            # Получаем chat_id из ссылки
            chat_entity = await self._resolve_chat_link(client, chat_link)
            if not chat_entity:
                logger.error(f"Не удалось найти чат по ссылке: {chat_link}")
                return []
            
            chat_id = chat_entity.id
            logger.info(f"Найден чат: {chat_entity.title} (ID: {chat_id})")
            
            # Применяем фильтры по умолчанию
            if filters is None:
                filters = {
                    'only_usernames': False,
                    'only_active': False,
                    'exclude_bots': False,
                    'exclude_premium': False
                }
            
            # Парсим участников
            offset = 0
            parsed_count = 0
            
            while parsed_count < limit:
                try:
                    # Получаем участников порциями
                    participants = await client.get_participants(
                        chat_entity,
                        limit=min(100, limit - parsed_count),
                        offset=offset
                    )
                    
                    if not participants:
                        break
                    
                    # Обрабатываем каждого участника
                    for participant in participants:
                        if parsed_count >= limit:
                            break
                        
                        try:
                            # Получаем информацию о пользоватеle
                            user_info = await self.get_user_info(client, participant.id)
                            
                            if not user_info:
                                continue
                            
                            # Применяем фильтры
                            if filters.get('only_usernames') and not user_info.get('username'):
                                continue
                            
                            if filters.get('exclude_bots') and user_info.get('is_bot'):
                                continue
                            
                            if filters.get('exclude_premium') and user_info.get('is_premium'):
                                continue
                            
                            # Проверка активности (если требуется)
                            if filters.get('only_active'):
                                # Проверяем статус пользователя
                                if hasattr(participant, 'status'):
                                    # Простая проверка - если статус не "давно не был онлайн"
                                    if hasattr(participant.status, '__class__'):
                                        status_class = participant.status.__class__.__name__
                                        if 'UserStatusLongTimeAgo' in status_class or 'UserStatusOffline' in status_class:
                                            # Проверяем дату последнего входа
                                            if hasattr(participant.status, 'was_online'):
                                                was_online = participant.status.was_online
                                                if was_online:
                                                    days_ago = (datetime.now(was_online.tzinfo) - was_online).days
                                                    if days_ago > 7:
                                                        continue
                            
                            # Сохраняем в БД
                            self._save_parsed_user(
                                user_id=user_info['id'],
                                username=user_info.get('username'),
                                first_name=user_info.get('first_name'),
                                last_name=user_info.get('last_name'),
                                phone=user_info.get('phone'),
                                chat_id=chat_id
                            )
                            
                            parsed_users.append(user_info)
                            parsed_count += 1
                            
                            # Логируем прогресс каждые 10 участников
                            if parsed_count % 10 == 0:
                                logger.info(f"Распарсено {parsed_count}/{limit} участников")
                            
                        except UserPrivacyRestrictedError:
                            logger.debug(f"Пользователь {participant.id} ограничил доступ к информации")
                            continue
                        except Exception as e:
                            logger.warning(f"Ошибка обработки участника {participant.id}: {e}")
                            continue
                    
                    offset += len(participants)
                    
                    # Если получили меньше участников, чем запросили - достигли конца
                    if len(participants) < 100:
                        break
                    
                except FloodWaitError as e:
                    logger.warning(f"FloodWait: нужно подождать {e.seconds} секунд")
                    await asyncio.sleep(e.seconds)
                    continue
                except ChatAdminRequiredError:
                    logger.error(f"Требуются права администратора для парсинга чата {chat_link}")
                    break
                except Exception as e:
                    logger.error(f"Ошибка получения участников: {e}", exc_info=True)
                    break
            
            logger.info(f"Парсинг завершён. Распарсено участников: {len(parsed_users)}")
            return parsed_users
            
        except Exception as e:
            logger.error(f"Ошибка парсинга чата {chat_link}: {e}", exc_info=True)
            return parsed_users
            
        finally:
            # Отключаемся в любом случае
            if client:
                await self.async_manager.disconnect(client)
    
    async def _resolve_chat_link(self, client: TelegramClient, chat_link: str):
        """
        Разрешает ссылку на чат в entity
        
        Args:
            client: Экземпляр TelegramClient
            chat_link: Ссылка на чат (@username или полная ссылка)
        
        Returns:
            Entity чата или None при ошибке
        """
        try:
            # Очищаем ссылку от лишних символов
            chat_link = chat_link.strip()
            
            # Убираем https://t.me/ или http://t.me/
            if 't.me/' in chat_link:
                chat_link = chat_link.split('t.me/')[-1]
            
            # Убираем @ если есть
            if chat_link.startswith('@'):
                chat_link = chat_link[1:]
            
            # Получаем entity
            entity = await client.get_entity(chat_link)
            return entity
            
        except UsernameNotOccupiedError:
            logger.error(f"Username не найден: {chat_link}")
            return None
        except ChannelPrivateError:
            logger.error(f"Канал приватный или недоступен: {chat_link}")
            return None
        except Exception as e:
            logger.error(f"Ошибка разрешения ссылки {chat_link}: {e}", exc_info=True)
            return None
    
    async def get_user_info(self, client: TelegramClient, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о пользователе
        
        Args:
            client: Экземпляр TelegramClient
            user_id: ID пользователя
        
        Returns:
            Словарь с информацией о пользователе или None при ошибке
        """
        try:
            # Получаем информацию о пользователе
            user = await client.get_entity(user_id)
            
            if not user:
                return None
            
            # Формируем результат
            user_info = {
                'id': user.id,
                'username': getattr(user, 'username', None),
                'first_name': getattr(user, 'first_name', None),
                'last_name': getattr(user, 'last_name', None),
                'phone': getattr(user, 'phone', None),
                'is_bot': getattr(user, 'bot', False),
                'is_premium': getattr(user, 'premium', False)
            }
            
            return user_info
            
        except UserPrivacyRestrictedError:
            logger.debug(f"Пользователь {user_id} ограничил доступ к информации")
            return None
        except Exception as e:
            logger.warning(f"Ошибка получения информации о пользователе {user_id}: {e}")
            return None
    
    def _save_parsed_user(
        self,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
        phone: Optional[str],
        chat_id: int
    ) -> None:
        """
        Сохраняет распарсенного пользователя в базу данных
        
        Args:
            user_id: ID пользователя
            username: Username пользователя
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            phone: Номер телефона пользователя
            chat_id: ID чата, из которого распарсен пользователь
        """
        try:
            # Проверяем, не существует ли уже такой пользователь из этого чата
            check_query = "SELECT id FROM parsed_users WHERE user_id = ? AND chat_id = ? LIMIT 1"
            existing = self.database.fetch_all(check_query, (user_id, chat_id))
            
            if existing:
                # Обновляем существующую запись
                update_query = """
                    UPDATE parsed_users 
                    SET username = ?, first_name = ?, last_name = ?, phone = ?, parsed_at = ?
                    WHERE user_id = ? AND chat_id = ?
                """
                parsed_at = datetime.now().isoformat()
                self.database.execute(
                    update_query,
                    (username, first_name, last_name, phone, parsed_at, user_id, chat_id)
                )
                logger.debug(f"Обновлён пользователь {user_id} из чата {chat_id}")
            else:
                # Создаём новую запись
                insert_query = """
                    INSERT INTO parsed_users (user_id, username, first_name, last_name, phone, chat_id, parsed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                parsed_at = datetime.now().isoformat()
                self.database.execute(
                    insert_query,
                    (user_id, username, first_name, last_name, phone, chat_id, parsed_at)
                )
                logger.debug(f"Сохранён пользователь {user_id} из чата {chat_id}")
                
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователя {user_id} в БД: {e}", exc_info=True)

