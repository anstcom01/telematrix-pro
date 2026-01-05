"""
TeleMatrix Pro - Главный файл приложения
Desktop приложение на PyQt6 для работы с Telegram через Telethon
"""

import sys
import logging
import asyncio
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMenuBar, QStatusBar, 
    QMessageBox, QMenu, QTabWidget, QLabel, QVBoxLayout, QWidget,
    QInputDialog
)
from PyQt6.QtCore import Qt
import qasync

from src.core.database import Database
from src.core.account_manager import AccountManager
from src.core.plugin_system import PluginSystem
from src.core.async_manager import AsyncManager

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
        self.async_manager = None
        
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
            
            # Создание менеджера асинхронных операций
            logger.info("Создание AsyncManager...")
            self.async_manager = AsyncManager(self.account_manager, self.database)
            logger.info("✅ AsyncManager создан")
            
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
    
    @qasync.asyncSlot(str)
    async def check_account_async(self, phone: str):
        """
        Асинхронная проверка аккаунта
        
        Args:
            phone: Номер телефона аккаунта для проверки
        """
        try:
            logger.info(f"Начало проверки аккаунта: {phone}")
            
            # Обновляем статус-бар
            self.statusBar.showMessage(f"Проверка аккаунта {phone}...")
            
            # Выполняем проверку через AsyncManager
            account_info = await self.async_manager.check_account(phone)
            
            # Формируем сообщение с результатом
            if account_info:
                message = f"✅ Аккаунт проверен успешно!\n\n"
                message += f"ID: {account_info.get('id', 'N/A')}\n"
                message += f"Username: @{account_info.get('username', 'N/A')}\n"
                message += f"Имя: {account_info.get('first_name', 'N/A')}\n"
                if account_info.get('last_name'):
                    message += f"Фамилия: {account_info.get('last_name')}\n"
                message += f"Телефон: {account_info.get('phone', 'N/A')}\n"
                message += f"Бот: {'Да' if account_info.get('is_bot') else 'Нет'}\n"
                message += f"Premium: {'Да' if account_info.get('is_premium') else 'Нет'}"
                
                QMessageBox.information(
                    self,
                    "Проверка аккаунта",
                    message
                )
                logger.info(f"Проверка аккаунта {phone} завершена успешно")
            else:
                QMessageBox.warning(
                    self,
                    "Проверка аккаунта",
                    f"Не удалось проверить аккаунт {phone}.\nВозможно, аккаунт не авторизован или произошла ошибка."
                )
                logger.warning(f"Проверка аккаунта {phone} не удалась")
            
            # Обновляем статус-бар
            self.statusBar.showMessage("Готов")
            
        except Exception as e:
            error_msg = f"Ошибка проверки аккаунта {phone}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            QMessageBox.critical(
                self,
                "Ошибка",
                error_msg
            )
            
            # Обновляем статус-бар
            self.statusBar.showMessage("Ошибка проверки")
    
    @qasync.asyncSlot(str)
    async def authenticate_account(self, phone: str):
        """
        Асинхронная авторизация аккаунта через Telethon
        
        Args:
            phone: Номер телефона аккаунта для авторизации
        """
        try:
            logger.info(f"Начало авторизации аккаунта: {phone}")
            
            # Получаем данные аккаунта
            account_data = self.account_manager.get_account_by_phone(phone)
            if not account_data:
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    f"Аккаунт {phone} не найден в базе данных"
                )
                return
            
            # Проверяем наличие session_string
            if account_data.get('session_string'):
                reply = QMessageBox.question(
                    self,
                    "Аккаунт уже авторизован",
                    f"Аккаунт {phone} уже имеет сохранённую сессию.\nПереавторизовать?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return
            
            # Обновляем статус-бар
            self.statusBar.showMessage(f"Авторизация аккаунта {phone}...")
            
            # Создаём клиента
            client = self.async_manager.create_client(phone)
            if not client:
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Не удалось создать клиент для {phone}"
                )
                return
            
            # Функция для получения кода через диалог
            def get_code_from_dialog(phone_number: str) -> str:
                code, ok = QInputDialog.getText(
                    self,
                    "Код подтверждения",
                    f"Введите код подтверждения для {phone_number}:",
                    echo=QInputDialog.EchoMode.Normal
                )
                if ok and code:
                    return code.strip()
                return ""
            
            # Функция для получения пароля 2FA через диалог
            def get_password_from_dialog(phone_number: str) -> str:
                password, ok = QInputDialog.getText(
                    self,
                    "Пароль 2FA",
                    f"Введите пароль 2FA для {phone_number}:",
                    echo=QInputDialog.EchoMode.Password
                )
                if ok and password:
                    return password.strip()
                return ""
            
            # Запускаем авторизацию
            success = await self.async_manager.start_client(
                client,
                phone,
                code_callback=get_code_from_dialog,
                password_callback=get_password_from_dialog
            )
            
            # Отключаем клиента
            await self.async_manager.disconnect(client)
            
            if success:
                QMessageBox.information(
                    self,
                    "Успех",
                    f"Аккаунт {phone} успешно авторизован!\nСессия сохранена в базе данных."
                )
                logger.info(f"Аккаунт {phone} успешно авторизован")
                
                # Обновляем таблицу в плагине Аккаунты, если он загружен
                self._refresh_accounts_plugin()
            else:
                QMessageBox.warning(
                    self,
                    "Ошибка авторизации",
                    f"Не удалось авторизовать аккаунт {phone}.\nПроверьте код подтверждения и попробуйте снова."
                )
                logger.warning(f"Авторизация аккаунта {phone} не удалась")
            
            # Обновляем статус-бар
            self.statusBar.showMessage("Готов")
            
        except Exception as e:
            error_msg = f"Ошибка авторизации аккаунта {phone}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            QMessageBox.critical(
                self,
                "Ошибка",
                error_msg
            )
            
            # Обновляем статус-бар
            self.statusBar.showMessage("Ошибка авторизации")
    
    def _refresh_accounts_plugin(self):
        """Обновляет таблицу аккаунтов в плагине Аккаунты"""
        try:
            # Находим виджет плагина Аккаунты
            for i in range(self.tabs.count()):
                widget = self.tabs.widget(i)
                if widget and hasattr(widget, 'load_accounts'):
                    widget.load_accounts()
                    logger.debug("Таблица аккаунтов обновлена")
                    break
        except Exception as e:
            logger.error(f"Ошибка обновления таблицы аккаунтов: {e}", exc_info=True)


def main():
    """Точка входа в приложение"""
    app = QApplication(sys.argv)
    
    # Настройка async event loop для PyQt6
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = MainApp()
    window.show()
    
    # Запускаем event loop
    with loop:
        sys.exit(loop.run_forever())


if __name__ == "__main__":
    main()
