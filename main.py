"""
TeleMatrix Pro - Главный файл приложения
Desktop приложение на PyQt6 для работы с Telegram через Telethon
"""

import sys
import logging
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMenuBar, QStatusBar, 
    QMessageBox, QMenu, QTabWidget, QLabel, QVBoxLayout, QWidget
)
from PyQt6.QtCore import Qt

from src.core.database import Database
from src.core.account_manager import AccountManager
from src.core.plugin_system import PluginSystem

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MainApp(QMainWindow):
    """Главное окно приложения TeleMatrix Pro"""
    
    def __init__(self):
        super().__init__()
        # Инициализация компонентов
        self.database = None
        self.account_manager = None
        self.plugin_system = None
        
        self.init_ui()
        self.init_core()
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        # Установка заголовка окна
        self.setWindowTitle("TeleMatrix Pro v1.2")
        
        # Установка минимального размера окна для адаптивности
        self.setMinimumSize(1000, 600)
        
        # Создание меню-бара
        self.create_menu_bar()
        
        # Создание статус-бара
        self.create_status_bar()
        
        # Создание вкладок для плагинов
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Центрирование окна на экране
        self.center_window()
        
        # Установка начального размера окна после центрирования
        self.resize(1400, 800)
    
    def create_menu_bar(self):
        """Создание меню-бара приложения"""
        menubar = self.menuBar()
        
        # Меню "Файл"
        file_menu = menubar.addMenu("Файл")
        # Здесь можно добавить пункты меню в будущем
        
        # Меню "Помощь"
        help_menu = menubar.addMenu("Помощь")
        # Здесь можно добавить пункты меню в будущем
        
        logger.info("Меню-бар создан")
    
    def create_status_bar(self):
        """Создание статус-бара"""
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Готов")
        logger.info("Статус-бар создан")
    
    def init_core(self):
        """Инициализация основных компонентов приложения"""
        try:
            logger.info("Инициализация основных компонентов...")
            
            # Создание базы данных
            logger.info("Создание базы данных...")
            self.database = Database("telematrix.db")
            self.database.connect()
            self.database.create_tables()
            logger.info("✅ База данных инициализирована")
            
            # Создание менеджера аккаунтов
            logger.info("Создание AccountManager...")
            self.account_manager = AccountManager(self.database)
            logger.info("✅ AccountManager создан")
            
            # Создание системы плагинов
            logger.info("Создание PluginSystem...")
            self.plugin_system = PluginSystem(self.account_manager, self.database)
            logger.info("✅ PluginSystem создан")
            
            # Загрузка плагинов
            logger.info("Загрузка плагинов...")
            plugins_count = self.plugin_system.load_plugins("src/plugins")
            logger.info(f"✅ Загружено плагинов: {plugins_count}")
            
            # Отображение плагинов во вкладках
            self.load_plugins_to_tabs()
            
            # Обновление статус-бара
            self.statusBar.showMessage(f"Готов | Плагинов: {plugins_count}")
            
            logger.info("✅ Все компоненты успешно инициализированы")
            
        except Exception as e:
            error_msg = f"Ошибка инициализации приложения: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Показываем сообщение об ошибке
            QMessageBox.critical(
                self,
                "Ошибка инициализации",
                error_msg
            )
            
            # Обновляем статус-бар
            self.statusBar.showMessage("Ошибка инициализации")
    
    def load_plugins_to_tabs(self):
        """Загружает плагины во вкладки интерфейса"""
        try:
            # Получаем список всех плагинов
            plugins = self.plugin_system.get_all_plugins()
            
            if not plugins:
                # Если плагинов нет, показываем заглушку
                placeholder = QWidget()
                layout = QVBoxLayout()
                label = QLabel("Плагины не найдены")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(label)
                placeholder.setLayout(layout)
                self.tabs.addTab(placeholder, "Нет плагинов")
                logger.warning("Плагины не найдены, показана заглушка")
                return
            
            # Добавляем каждый плагин как вкладку
            for plugin_info in plugins:
                plugin_name = plugin_info['name']
                
                # Создаём виджет плагина
                widget = self.plugin_system.get_plugin_widget(plugin_name)
                
                if widget is None:
                    logger.warning(f"Не удалось создать виджет для плагина: {plugin_name}")
                    continue
                
                # Получаем информацию о плагине
                if hasattr(widget, 'get_info'):
                    info = widget.get_info()
                    tab_label = f"{info['icon']} {info['name']}"
                else:
                    # Если метод get_info отсутствует, используем данные из списка
                    tab_label = f"{plugin_info['icon']} {plugin_info['name']}"
                
                # Добавляем вкладку
                self.tabs.addTab(widget, tab_label)
                logger.info(f"✅ Добавлена вкладка: {tab_label}")
            
            logger.info(f"✅ Всего вкладок создано: {self.tabs.count()}")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки плагинов во вкладки: {e}", exc_info=True)
            # Показываем заглушку при ошибке
            placeholder = QWidget()
            layout = QVBoxLayout()
            label = QLabel(f"Ошибка загрузки плагинов: {str(e)}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            placeholder.setLayout(layout)
            self.tabs.addTab(placeholder, "Ошибка")
    
    def center_window(self):
        """Центрирует окно на экране"""
        # Получаем геометрию экрана
        screen = self.screen().availableGeometry()
        # Получаем геометрию окна
        window = self.frameGeometry()
        # Вычисляем центр экрана
        center_point = screen.center()
        # Перемещаем центр окна в центр экрана
        window.moveCenter(center_point)
        # Устанавливаем позицию окна
        self.move(window.topLeft())


def main():
    """Точка входа в приложение"""
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
