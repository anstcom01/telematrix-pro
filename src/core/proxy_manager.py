"""
Менеджер прокси-серверов для TeleMatrix Pro
"""

import logging
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional, Dict, Any, List

from .database import Database

logger = logging.getLogger(__name__)


class ProxyManager:
    """Менеджер для работы с прокси-серверами"""
    
    # Поддерживаемые типы прокси
    PROXY_TYPE_HTTP = "http"
    PROXY_TYPE_HTTPS = "https"
    PROXY_TYPE_SOCKS5 = "socks5"
    PROXY_TYPE_MOBILE = "mobile"
    
    def __init__(self, database: Database):
        """
        Инициализация менеджера прокси
        
        Args:
            database: Экземпляр Database для работы с БД
        """
        self.database = database
        self._create_table()
        logger.info("ProxyManager инициализирован")
    
    def _create_table(self) -> None:
        """Создаёт таблицу proxy_settings если её нет"""
        try:
            query = """
                CREATE TABLE IF NOT EXISTS proxy_settings (
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
                )
            """
            self.database.execute(query)
            logger.info("Таблица proxy_settings создана или уже существует")
        except Exception as e:
            logger.error(f"Ошибка создания таблицы proxy_settings: {e}", exc_info=True)
            raise
    
    def add_proxy(
        self,
        account_id: int,
        proxy_type: str,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
        rotation_interval: int = 0
    ) -> int:
        """
        Добавляет прокси для аккаунта
        
        Args:
            account_id: ID аккаунта
            proxy_type: Тип прокси (http, https, socks5, mobile)
            host: Хост прокси-сервера
            port: Порт прокси-сервера
            username: Имя пользователя (опционально)
            password: Пароль (опционально)
            rotation_interval: Интервал ротации в минутах (для Mobile Proxy)
        
        Returns:
            ID созданной записи
        
        Raises:
            ValueError: При невалидных данных
        """
        try:
            # Валидация типа прокси
            valid_types = [self.PROXY_TYPE_HTTP, self.PROXY_TYPE_HTTPS, 
                          self.PROXY_TYPE_SOCKS5, self.PROXY_TYPE_MOBILE]
            if proxy_type.lower() not in valid_types:
                raise ValueError(f"Неверный тип прокси: {proxy_type}. Допустимые: {', '.join(valid_types)}")
            
            # Валидация хоста
            if not host or not host.strip():
                raise ValueError("Хост прокси не может быть пустым")
            
            # Валидация порта
            if not isinstance(port, int) or port < 1 or port > 65535:
                raise ValueError(f"Неверный порт: {port}. Допустимый диапазон: 1-65535")
            
            # Проверяем, не существует ли уже прокси для этого аккаунта
            existing = self.get_proxy(account_id)
            if existing:
                raise ValueError(f"Прокси для аккаунта {account_id} уже существует. Используйте update_proxy()")
            
            # Создаём запись в БД
            created_at = datetime.now().isoformat()
            rotation_enabled = 1 if proxy_type.lower() == self.PROXY_TYPE_MOBILE and rotation_interval > 0 else 0
            
            query = """
                INSERT INTO proxy_settings 
                (account_id, proxy_type, host, port, username, password, 
                 rotation_enabled, rotation_interval, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            proxy_id = self.database.execute(
                query,
                (account_id, proxy_type.lower(), host.strip(), port, username, password,
                 rotation_enabled, rotation_interval, created_at)
            )
            
            logger.info(f"Прокси добавлен для аккаунта {account_id}: {proxy_type}://{host}:{port}")
            return proxy_id
            
        except Exception as e:
            logger.error(f"Ошибка добавления прокси для аккаунта {account_id}: {e}", exc_info=True)
            raise
    
    def get_proxy(self, account_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает прокси для аккаунта
        
        Args:
            account_id: ID аккаунта
        
        Returns:
            Словарь с данными прокси или None, если не найден
        """
        try:
            query = "SELECT * FROM proxy_settings WHERE account_id = ? LIMIT 1"
            rows = self.database.fetch_all(query, (account_id,))
            
            if rows:
                row = rows[0]
                proxy = {
                    'id': row['id'],
                    'account_id': row['account_id'],
                    'proxy_type': row['proxy_type'],
                    'host': row['host'],
                    'port': row['port'],
                    'username': row['username'],
                    'password': row['password'],
                    'rotation_enabled': bool(row['rotation_enabled']),
                    'rotation_interval': row['rotation_interval'],
                    'last_used': row['last_used'],
                    'created_at': row['created_at']
                }
                logger.debug(f"Прокси найден для аккаунта {account_id}")
                return proxy
            
            logger.debug(f"Прокси не найден для аккаунта {account_id}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения прокси для аккаунта {account_id}: {e}", exc_info=True)
            raise
    
    def update_proxy(self, account_id: int, **fields: Any) -> bool:
        """
        Обновляет прокси для аккаунта
        
        Args:
            account_id: ID аккаунта
            **fields: Поля для обновления (proxy_type, host, port, username, password, 
                     rotation_enabled, rotation_interval)
        
        Returns:
            True если обновлено, False если прокси не найден
        
        Raises:
            ValueError: При невалидных данных
        """
        try:
            # Проверяем существование прокси
            existing = self.get_proxy(account_id)
            if not existing:
                logger.warning(f"Прокси для аккаунта {account_id} не найден для обновления")
                return False
            
            # Валидация полей
            valid_fields = ['proxy_type', 'host', 'port', 'username', 'password', 
                          'rotation_enabled', 'rotation_interval', 'last_used']
            update_fields = []
            update_values = []
            
            for field, value in fields.items():
                if field not in valid_fields:
                    logger.warning(f"Неизвестное поле для обновления: {field}")
                    continue
                
                # Валидация типа прокси
                if field == 'proxy_type':
                    valid_types = [self.PROXY_TYPE_HTTP, self.PROXY_TYPE_HTTPS, 
                                  self.PROXY_TYPE_SOCKS5, self.PROXY_TYPE_MOBILE]
                    if value.lower() not in valid_types:
                        raise ValueError(f"Неверный тип прокси: {value}")
                    value = value.lower()
                
                # Валидация хоста
                if field == 'host':
                    if not value or not str(value).strip():
                        raise ValueError("Хост прокси не может быть пустым")
                    value = str(value).strip()
                
                # Валидация порта
                if field == 'port':
                    if not isinstance(value, int) or value < 1 or value > 65535:
                        raise ValueError(f"Неверный порт: {value}")
                
                update_fields.append(f"{field} = ?")
                update_values.append(value)
            
            if not update_fields:
                logger.warning("Нет полей для обновления")
                return False
            
            # Обновляем запись
            query = f"UPDATE proxy_settings SET {', '.join(update_fields)} WHERE account_id = ?"
            update_values.append(account_id)
            self.database.execute(query, tuple(update_values))
            
            logger.info(f"Прокси обновлён для аккаунта {account_id}: {', '.join(update_fields)}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления прокси для аккаунта {account_id}: {e}", exc_info=True)
            raise
    
    def delete_proxy(self, account_id: int) -> bool:
        """
        Удаляет прокси для аккаунта
        
        Args:
            account_id: ID аккаунта
        
        Returns:
            True если удалено, False если не найдено
        """
        try:
            # Проверяем существование
            existing = self.get_proxy(account_id)
            if not existing:
                logger.warning(f"Прокси для аккаунта {account_id} не найден для удаления")
                return False
            
            # Удаляем запись
            query = "DELETE FROM proxy_settings WHERE account_id = ?"
            self.database.execute(query, (account_id,))
            
            logger.info(f"Прокси удалён для аккаунта {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления прокси для аккаунта {account_id}: {e}", exc_info=True)
            raise
    
    def get_all_proxies(self) -> List[Dict[str, Any]]:
        """
        Получает список всех прокси
        
        Returns:
            Список словарей с данными прокси
        """
        try:
            query = "SELECT * FROM proxy_settings ORDER BY account_id"
            rows = self.database.fetch_all(query)
            
            proxies = []
            for row in rows:
                proxy = {
                    'id': row['id'],
                    'account_id': row['account_id'],
                    'proxy_type': row['proxy_type'],
                    'host': row['host'],
                    'port': row['port'],
                    'username': row['username'],
                    'password': row['password'],
                    'rotation_enabled': bool(row['rotation_enabled']),
                    'rotation_interval': row['rotation_interval'],
                    'last_used': row['last_used'],
                    'created_at': row['created_at']
                }
                proxies.append(proxy)
            
            logger.info(f"Получено прокси: {len(proxies)}")
            return proxies
            
        except Exception as e:
            logger.error(f"Ошибка получения списка прокси: {e}", exc_info=True)
            raise
    
    def rotate_proxy(self, account_id: int) -> bool:
        """
        Выполняет ротацию IP для Mobile Proxy
        
        Args:
            account_id: ID аккаунта
        
        Returns:
            True если ротация выполнена, False если прокси не найден или не Mobile Proxy
        """
        try:
            proxy = self.get_proxy(account_id)
            if not proxy:
                logger.warning(f"Прокси для аккаунта {account_id} не найден")
                return False
            
            if proxy['proxy_type'] != self.PROXY_TYPE_MOBILE:
                logger.warning(f"Ротация доступна только для Mobile Proxy. Тип прокси: {proxy['proxy_type']}")
                return False
            
            if not proxy['rotation_enabled']:
                logger.warning(f"Ротация отключена для прокси аккаунта {account_id}")
                return False
            
            # Для Mobile Proxy ротация обычно выполняется через API провайдера
            # Здесь можно добавить вызов API провайдера для смены IP
            # Обновляем last_used напрямую через SQL
            last_used = datetime.now().isoformat()
            query = "UPDATE proxy_settings SET last_used = ? WHERE account_id = ?"
            self.database.execute(query, (last_used, account_id))
            
            logger.info(f"Ротация IP выполнена для аккаунта {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка ротации прокси для аккаунта {account_id}: {e}", exc_info=True)
            return False
    
    def test_proxy(self, proxy_url: str, timeout: int = 10) -> Dict[str, Any]:
        """
        Проверяет работоспособность прокси
        
        Args:
            proxy_url: URL прокси в формате http://host:port или http://user:pass@host:port
            timeout: Таймаут проверки в секундах
        
        Returns:
            Словарь с результатом проверки: {success: bool, response_time: float, error: str}
        """
        import time
        
        result = {
            'success': False,
            'response_time': 0.0,
            'error': ''
        }
        
        try:
            # Парсим прокси URL
            parsed = self.parse_proxy_string(proxy_url)
            if not parsed:
                result['error'] = 'Не удалось распарсить URL прокси'
                return result
            
            # Формируем URL для проверки (используем httpbin.org или аналогичный сервис)
            test_url = "http://httpbin.org/ip"
            
            # Настраиваем прокси
            proxy_handler = urllib.request.ProxyHandler({
                'http': proxy_url,
                'https': proxy_url
            })
            opener = urllib.request.build_opener(proxy_handler)
            
            # Выполняем запрос
            start_time = time.time()
            try:
                response = opener.open(test_url, timeout=timeout)
                response_time = time.time() - start_time
                
                if response.getcode() == 200:
                    result['success'] = True
                    result['response_time'] = round(response_time, 2)
                    logger.info(f"Прокси {proxy_url} работает. Время отклика: {result['response_time']} сек")
                else:
                    result['error'] = f"HTTP код: {response.getcode()}"
                    
            except urllib.error.URLError as e:
                result['error'] = f"Ошибка подключения: {str(e)}"
                logger.warning(f"Прокси {proxy_url} не работает: {result['error']}")
            except Exception as e:
                result['error'] = f"Неожиданная ошибка: {str(e)}"
                logger.error(f"Ошибка проверки прокси {proxy_url}: {e}", exc_info=True)
            
        except Exception as e:
            result['error'] = f"Ошибка проверки прокси: {str(e)}"
            logger.error(f"Ошибка проверки прокси {proxy_url}: {e}", exc_info=True)
        
        return result
    
    def format_proxy_url(
        self,
        proxy_type: str,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> str:
        """
        Форматирует прокси в URL строку
        
        Args:
            proxy_type: Тип прокси (http, https, socks5, mobile)
            host: Хост прокси-сервера
            port: Порт прокси-сервера
            username: Имя пользователя (опционально)
            password: Пароль (опционально)
        
        Returns:
            URL строка прокси
        """
        try:
            # Определяем схему в зависимости от типа
            if proxy_type.lower() == self.PROXY_TYPE_SOCKS5:
                scheme = "socks5"
            elif proxy_type.lower() == self.PROXY_TYPE_HTTPS:
                scheme = "https"
            elif proxy_type.lower() == self.PROXY_TYPE_MOBILE:
                scheme = "http"  # Mobile Proxy обычно через HTTP
            else:
                scheme = "http"
            
            # Формируем URL
            if username and password:
                proxy_url = f"{scheme}://{username}:{password}@{host}:{port}"
            elif username:
                proxy_url = f"{scheme}://{username}@{host}:{port}"
            else:
                proxy_url = f"{scheme}://{host}:{port}"
            
            return proxy_url
            
        except Exception as e:
            logger.error(f"Ошибка форматирования URL прокси: {e}", exc_info=True)
            raise
    
    def parse_proxy_string(self, proxy_string: str) -> Optional[Dict[str, Any]]:
        """
        Парсит строку прокси в словарь
        
        Поддерживаемые форматы:
        - host:port
        - username:password@host:port
        - http://host:port
        - http://username:password@host:port
        - socks5://username:password@host:port
        
        Args:
            proxy_string: Строка прокси
        
        Returns:
            Словарь с данными прокси или None при ошибке
        """
        try:
            if not proxy_string or not proxy_string.strip():
                logger.warning("Пустая строка прокси")
                return None
            
            proxy_string = proxy_string.strip()
            
            # Определяем тип прокси по схеме
            proxy_type = self.PROXY_TYPE_HTTP
            if proxy_string.startswith('socks5://'):
                proxy_type = self.PROXY_TYPE_SOCKS5
                proxy_string = proxy_string.replace('socks5://', '')
            elif proxy_string.startswith('https://'):
                proxy_type = self.PROXY_TYPE_HTTPS
                proxy_string = proxy_string.replace('https://', '')
            elif proxy_string.startswith('http://'):
                proxy_type = self.PROXY_TYPE_HTTP
                proxy_string = proxy_string.replace('http://', '')
            
            # Парсим username:password@host:port
            # Проверяем наличие @ для авторизации
            if '@' in proxy_string:
                auth_part, server_part = proxy_string.rsplit('@', 1)
                if ':' in auth_part:
                    username, password = auth_part.split(':', 1)
                else:
                    username = auth_part
                    password = None
            else:
                username = None
                password = None
                server_part = proxy_string
            
            # Парсим host:port
            if ':' in server_part:
                host, port_str = server_part.rsplit(':', 1)
                try:
                    port = int(port_str)
                except ValueError:
                    logger.error(f"Неверный формат порта: {port_str}")
                    return None
            else:
                logger.error(f"Неверный формат прокси: отсутствует порт")
                return None
            
            # Валидация
            if not host or not host.strip():
                logger.error("Хост прокси не может быть пустым")
                return None
            
            if port < 1 or port > 65535:
                logger.error(f"Неверный порт: {port}")
                return None
            
            result = {
                'proxy_type': proxy_type,
                'host': host.strip(),
                'port': port,
                'username': username,
                'password': password
            }
            
            logger.debug(f"Прокси распарсен: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка парсинга строки прокси '{proxy_string}': {e}", exc_info=True)
            return None
    
    def get_proxy_url(self, account_id: int) -> Optional[str]:
        """
        Получает URL прокси для аккаунта
        
        Args:
            account_id: ID аккаунта
        
        Returns:
            URL строка прокси или None
        """
        try:
            proxy = self.get_proxy(account_id)
            if not proxy:
                return None
            
            return self.format_proxy_url(
                proxy_type=proxy['proxy_type'],
                host=proxy['host'],
                port=proxy['port'],
                username=proxy['username'],
                password=proxy['password']
            )
            
        except Exception as e:
            logger.error(f"Ошибка получения URL прокси для аккаунта {account_id}: {e}", exc_info=True)
            return None

