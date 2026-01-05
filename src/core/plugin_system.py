"""
Система загрузки и управления плагинами для TeleMatrix Pro
"""

import logging
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Type
from PyQt6.QtWidgets import QWidget

from .account_manager import AccountManager
from .database import Database

logger = logging.getLogger(__name__)


class PluginSystem:
    """Система загрузки и управления плагинами"""
    
    def __init__(self, account_manager: AccountManager, database: Database):
        """
        Инициализация системы плагинов
        
        Args:
            account_manager: Экземпляр AccountManager для передачи в плагины
            database: Экземпляр Database для передачи в плагины
        """
        self.account_manager = account_manager
        self.database = database
        self.plugins: Dict[str, Dict[str, Any]] = {}
        logger.info("PluginSystem инициализирован")
    
    def load_plugins(self, plugins_dir: Optional[str] = None) -> int:
        """
        Сканирует папку с плагинами и загружает их
        
        Args:
            plugins_dir: Путь к папке с плагинами (по умолчанию src/plugins/)
        
        Returns:
            Количество успешно загруженных плагинов
        """
        if plugins_dir is None:
            # Путь относительно корня проекта
            project_root = Path(__file__).parent.parent.parent
            plugins_dir = project_root / "src" / "plugins"
        else:
            plugins_dir = Path(plugins_dir)
        
        if not plugins_dir.exists():
            logger.warning(f"Папка с плагинами не найдена: {plugins_dir}")
            return 0
        
        logger.info(f"Сканирование папки плагинов: {plugins_dir}")
        loaded_count = 0
        
        # Сканируем все подпапки в директории плагинов
        for plugin_folder in plugins_dir.iterdir():
            if not plugin_folder.is_dir():
                continue
            
            # Пропускаем служебные папки
            if plugin_folder.name.startswith('_'):
                continue
            
            widget_file = plugin_folder / "widget.py"
            
            if not widget_file.exists():
                logger.debug(f"Плагин {plugin_folder.name} не содержит widget.py, пропуск")
                continue
            
            # Пытаемся загрузить плагин
            try:
                plugin_info = self._load_plugin(plugin_folder)
                if plugin_info:
                    plugin_name = plugin_info['name']
                    self.plugins[plugin_name] = plugin_info
                    loaded_count += 1
                    logger.info(f"✅ Плагин загружен: {plugin_name}")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки плагина {plugin_folder.name}: {e}", exc_info=True)
        
        logger.info(f"Загружено плагинов: {loaded_count}")
        return loaded_count
    
    def _load_plugin(self, plugin_folder: Path) -> Optional[Dict[str, Any]]:
        """
        Загружает отдельный плагин из папки
        
        Args:
            plugin_folder: Путь к папке плагина
        
        Returns:
            Словарь с информацией о плагине или None при ошибке
        
        Raises:
            Exception: При ошибке загрузки плагина
        """
        plugin_name = plugin_folder.name
        
        # Формируем имя модуля для импорта
        # Например: src.plugins.example_plugin.widget
        module_path = f"src.plugins.{plugin_name}.widget"
        
        try:
            # Динамический импорт модуля
            if module_path in sys.modules:
                # Если модуль уже загружен, перезагружаем его
                importlib.reload(sys.modules[module_path])
            else:
                spec = importlib.util.spec_from_file_location(
                    module_path,
                    plugin_folder / "widget.py"
                )
                if spec is None or spec.loader is None:
                    raise ImportError(f"Не удалось создать spec для модуля {module_path}")
                
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_path] = module
                spec.loader.exec_module(module)
            
            # Ищем класс наследующий QWidget
            widget_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, QWidget) and 
                    attr != QWidget):
                    widget_class = attr
                    break
            
            if widget_class is None:
                raise ValueError(f"В модуле {module_path} не найден класс наследующий QWidget")
            
            # Получаем информацию о плагине через метод get_info()
            # Создаём временный экземпляр для получения информации
            try:
                # Пытаемся создать экземпляр с параметрами
                temp_widget = widget_class(self.account_manager, self.database)
            except TypeError:
                # Если конструктор не принимает параметры, создаём без них
                temp_widget = widget_class()
            
            if not hasattr(temp_widget, 'get_info'):
                raise ValueError(f"Класс {widget_class.__name__} не имеет метода get_info()")
            
            plugin_info = temp_widget.get_info()
            
            # Проверяем структуру информации
            required_keys = ['name', 'icon', 'description']
            for key in required_keys:
                if key not in plugin_info:
                    raise ValueError(f"Метод get_info() не возвращает обязательный ключ: {key}")
            
            # Сохраняем класс виджета и путь к модулю
            return {
                'name': plugin_info['name'],
                'icon': plugin_info['icon'],
                'description': plugin_info['description'],
                'widget_class': widget_class,
                'module_path': module_path,
                'folder': str(plugin_folder)
            }
            
        except Exception as e:
            logger.error(f"Ошибка загрузки плагина {plugin_name}: {e}", exc_info=True)
            raise
    
    def get_all_plugins(self) -> List[Dict[str, Any]]:
        """
        Возвращает список всех загруженных плагинов
        
        Returns:
            Список словарей с информацией о плагинах
        """
        plugins_list = []
        for plugin_name, plugin_info in self.plugins.items():
            plugins_list.append({
                'name': plugin_info['name'],
                'icon': plugin_info['icon'],
                'description': plugin_info['description']
            })
        
        logger.debug(f"Запрошен список плагинов: {len(plugins_list)}")
        return plugins_list
    
    def get_plugin_widget(self, plugin_name: str) -> Optional[QWidget]:
        """
        Создаёт виджет плагина по имени
        
        Args:
            plugin_name: Имя плагина
        
        Returns:
            Экземпляр виджета плагина или None, если плагин не найден
        """
        if plugin_name not in self.plugins:
            logger.warning(f"Плагин не найден: {plugin_name}")
            return None
        
        plugin_info = self.plugins[plugin_name]
        widget_class = plugin_info['widget_class']
        
        try:
            # Пытаемся создать виджет с параметрами
            try:
                widget = widget_class(self.account_manager, self.database)
            except TypeError:
                # Если конструктор не принимает параметры, создаём без них
                widget = widget_class()
            
            logger.info(f"Виджет плагина создан: {plugin_name}")
            return widget
            
        except Exception as e:
            logger.error(f"Ошибка создания виджета плагина {plugin_name}: {e}", exc_info=True)
            return None

