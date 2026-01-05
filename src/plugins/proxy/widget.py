"""
Виджет плагина "Прокси" для настройки прокси-серверов для аккаунтов
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QSpinBox, QPushButton, QTextEdit, QLabel, QGroupBox,
    QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt

from src.core.account_manager import AccountManager
from src.core.database import Database
from src.core.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)


class ProxyWidget(QWidget):
    """Виджет для настройки прокси-серверов для аккаунтов"""
    
    def __init__(self, account_manager: AccountManager, database: Database):
        """
        Инициализация виджета прокси
        
        Args:
            account_manager: Экземпляр AccountManager для работы с аккаунтами
            database: Экземпляр Database для работы с БД
        """
        super().__init__()
        self.account_manager = account_manager
        self.database = database
        self.proxy_manager = ProxyManager(database)
        self.current_account_id = None
        self.init_ui()
        self.load_accounts()
        self.load_proxies()
        logger.info("ProxyWidget инициализирован")
    
    @staticmethod
    def get_info():
        """
        Возвращает информацию о плагине
        
        Returns:
            Словарь с информацией о плагине
        """
        return {
            "name": "Прокси",
            "icon": "🔌",
            "description": "Настройка прокси-серверов для аккаунтов"
        }
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        main_layout = QHBoxLayout()
        
        # ЛЕВАЯ ПАНЕЛЬ "Настройка прокси"
        settings_group = QGroupBox("Настройка прокси")
        settings_layout = QVBoxLayout()
        
        # Выбор аккаунта
        account_label = QLabel("Выбрать аккаунт:")
        self.account_combo = QComboBox()
        self.account_combo.currentIndexChanged.connect(self.on_account_changed)
        settings_layout.addWidget(account_label)
        settings_layout.addWidget(self.account_combo)
        
        # Тип прокси
        proxy_type_label = QLabel("Тип прокси:")
        self.proxy_type_combo = QComboBox()
        self.proxy_type_combo.addItems(["HTTP", "SOCKS5", "Mobile"])
        settings_layout.addWidget(proxy_type_label)
        settings_layout.addWidget(self.proxy_type_combo)
        
        # Хост
        host_label = QLabel("Хост:")
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("example.com")
        settings_layout.addWidget(host_label)
        settings_layout.addWidget(self.host_input)
        
        # Порт
        port_label = QLabel("Порт:")
        port_layout = QHBoxLayout()
        self.port_spinbox = QSpinBox()
        self.port_spinbox.setMinimum(1)
        self.port_spinbox.setMaximum(65535)
        self.port_spinbox.setValue(8080)
        port_layout.addWidget(self.port_spinbox)
        port_layout.addStretch()
        settings_layout.addWidget(port_label)
        settings_layout.addLayout(port_layout)
        
        # Логин
        username_label = QLabel("Логин (опционально):")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("username")
        settings_layout.addWidget(username_label)
        settings_layout.addWidget(self.username_input)
        
        # Пароль
        password_label = QLabel("Пароль (опционально):")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("password")
        settings_layout.addWidget(password_label)
        settings_layout.addWidget(self.password_input)
        
        # Ротация IP
        self.rotation_checkbox = QCheckBox("Ротация IP")
        self.rotation_checkbox.stateChanged.connect(self.on_rotation_changed)
        settings_layout.addWidget(self.rotation_checkbox)
        
        # Интервал ротации
        rotation_interval_label = QLabel("Интервал ротации (сек):")
        rotation_interval_layout = QHBoxLayout()
        self.rotation_interval_spinbox = QSpinBox()
        self.rotation_interval_spinbox.setMinimum(1)
        self.rotation_interval_spinbox.setMaximum(86400)
        self.rotation_interval_spinbox.setValue(300)
        self.rotation_interval_spinbox.setEnabled(False)
        rotation_interval_layout.addWidget(self.rotation_interval_spinbox)
        rotation_interval_layout.addStretch()
        settings_layout.addWidget(rotation_interval_label)
        settings_layout.addLayout(rotation_interval_layout)
        
        settings_layout.addStretch()
        
        # Кнопки действий
        buttons_layout = QVBoxLayout()
        
        self.test_button = QPushButton("🧪 Протестировать прокси")
        self.test_button.clicked.connect(self.test_proxy)
        buttons_layout.addWidget(self.test_button)
        
        self.save_button = QPushButton("✅ Сохранить")
        self.save_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.save_button.clicked.connect(self.save_proxy)
        buttons_layout.addWidget(self.save_button)
        
        self.delete_button = QPushButton("🗑️ Удалить")
        self.delete_button.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.delete_button.clicked.connect(self.delete_selected_proxy)
        buttons_layout.addWidget(self.delete_button)
        
        settings_layout.addLayout(buttons_layout)
        settings_group.setLayout(settings_layout)
        
        # ПРАВАЯ ПАНЕЛЬ "Список прокси"
        list_group = QGroupBox("Список прокси")
        list_layout = QVBoxLayout()
        
        # Таблица прокси
        self.proxies_table = QTableWidget()
        self.proxies_table.setColumnCount(5)
        self.proxies_table.setHorizontalHeaderLabels(["Аккаунт", "Тип", "Хост:Порт", "Ротация", "Статус"])
        self.proxies_table.horizontalHeader().setStretchLastSection(True)
        self.proxies_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.proxies_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        list_layout.addWidget(self.proxies_table)
        
        # Кнопка обновления
        refresh_button = QPushButton("↻ Обновить список")
        refresh_button.clicked.connect(self.load_proxies)
        list_layout.addWidget(refresh_button)
        
        # Логи
        logs_label = QLabel("Логи:")
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setMaximumHeight(150)
        list_layout.addWidget(logs_label)
        list_layout.addWidget(self.logs_text)
        
        list_group.setLayout(list_layout)
        
        # Добавляем группы в основной layout
        main_layout.addWidget(settings_group, 40)  # Левая панель 40%
        main_layout.addWidget(list_group, 60)       # Правая панель 60%
        
        self.setLayout(main_layout)
    
    def load_accounts(self):
        """Загружает список аккаунтов в QComboBox"""
        try:
            accounts = self.account_manager.get_all_accounts()
            self.account_combo.clear()
            self.account_combo.addItem("-- Выберите аккаунт --", None)
            
            for account in accounts:
                display_text = f"{account['phone']} (ID: {account['id']})"
                self.account_combo.addItem(display_text, account['id'])
            
            self.log_message(f"✅ Загружено аккаунтов: {len(accounts)}")
            logger.info(f"Загружено аккаунтов: {len(accounts)}")
            
        except Exception as e:
            error_msg = f"Ошибка загрузки аккаунтов: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_message(f"❌ {error_msg}")
    
    def load_proxies(self):
        """Загружает все прокси в таблицу"""
        try:
            proxies = self.proxy_manager.get_all_proxies()
            accounts = self.account_manager.get_all_accounts()
            
            # Создаём словарь для быстрого поиска аккаунтов
            accounts_dict = {acc['id']: acc for acc in accounts}
            
            # Очищаем таблицу
            self.proxies_table.setRowCount(0)
            
            # Заполняем таблицу
            for proxy in proxies:
                row = self.proxies_table.rowCount()
                self.proxies_table.insertRow(row)
                
                # Аккаунт
                account_id = proxy['account_id']
                account_info = accounts_dict.get(account_id, {})
                account_text = account_info.get('phone', f"ID: {account_id}")
                self.proxies_table.setItem(row, 0, QTableWidgetItem(account_text))
                
                # Тип прокси
                proxy_type = proxy['proxy_type'].upper()
                self.proxies_table.setItem(row, 1, QTableWidgetItem(proxy_type))
                
                # Хост:Порт
                host_port = f"{proxy['host']}:{proxy['port']}"
                self.proxies_table.setItem(row, 2, QTableWidgetItem(host_port))
                
                # Ротация
                rotation_text = "Да" if proxy['rotation_enabled'] else "Нет"
                self.proxies_table.setItem(row, 3, QTableWidgetItem(rotation_text))
                
                # Статус (пока placeholder)
                status_text = "Активен"
                self.proxies_table.setItem(row, 4, QTableWidgetItem(status_text))
            
            self.log_message(f"✅ Загружено прокси: {len(proxies)}")
            logger.info(f"Загружено прокси: {len(proxies)}")
            
        except Exception as e:
            error_msg = f"Ошибка загрузки прокси: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_message(f"❌ {error_msg}")
    
    def on_account_changed(self):
        """Обработчик изменения выбранного аккаунта"""
        try:
            account_id = self.account_combo.currentData()
            self.current_account_id = account_id
            
            if account_id is None:
                # Очищаем поля
                self.clear_fields()
                return
            
            # Загружаем прокси для выбранного аккаунта
            proxy = self.proxy_manager.get_proxy(account_id)
            
            if proxy:
                # Заполняем поля данными прокси
                self.proxy_type_combo.setCurrentText(proxy['proxy_type'].upper())
                self.host_input.setText(proxy['host'])
                self.port_spinbox.setValue(proxy['port'])
                self.username_input.setText(proxy['username'] or '')
                self.password_input.setText(proxy['password'] or '')
                self.rotation_checkbox.setChecked(proxy['rotation_enabled'])
                self.rotation_interval_spinbox.setValue(proxy['rotation_interval'] or 300)
                self.rotation_interval_spinbox.setEnabled(proxy['rotation_enabled'])
                
                self.log_message(f"✅ Загружен прокси для аккаунта {account_id}")
            else:
                # Очищаем поля для нового прокси
                self.clear_fields()
                self.log_message(f"ℹ️ Прокси для аккаунта {account_id} не найден. Можно добавить новый.")
            
        except Exception as e:
            error_msg = f"Ошибка загрузки прокси для аккаунта: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_message(f"❌ {error_msg}")
    
    def clear_fields(self):
        """Очищает все поля формы"""
        self.proxy_type_combo.setCurrentIndex(0)
        self.host_input.clear()
        self.port_spinbox.setValue(8080)
        self.username_input.clear()
        self.password_input.clear()
        self.rotation_checkbox.setChecked(False)
        self.rotation_interval_spinbox.setValue(300)
        self.rotation_interval_spinbox.setEnabled(False)
    
    def on_rotation_changed(self, state):
        """Обработчик изменения состояния чекбокса ротации"""
        # state: 0 = Unchecked, 2 = Checked
        self.rotation_interval_spinbox.setEnabled(self.rotation_checkbox.isChecked())
    
    def validate_fields(self) -> bool:
        """
        Валидирует поля формы
        
        Returns:
            True если валидация прошла успешно
        """
        # Проверка выбора аккаунта
        if self.current_account_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите аккаунт")
            return False
        
        # Проверка хоста
        host = self.host_input.text().strip()
        if not host:
            QMessageBox.warning(self, "Ошибка", "Введите хост прокси")
            return False
        
        # Проверка порта
        port = self.port_spinbox.value()
        if port < 1 or port > 65535:
            QMessageBox.warning(self, "Ошибка", "Неверный порт. Допустимый диапазон: 1-65535")
            return False
        
        return True
    
    def save_proxy(self):
        """Сохраняет прокси для выбранного аккаунта"""
        try:
            if not self.validate_fields():
                return
            
            account_id = self.current_account_id
            proxy_type = self.proxy_type_combo.currentText().lower()
            host = self.host_input.text().strip()
            port = self.port_spinbox.value()
            username = self.username_input.text().strip() or None
            password = self.password_input.text().strip() or None
            rotation_enabled = self.rotation_checkbox.isChecked()
            rotation_interval = self.rotation_interval_spinbox.value() if rotation_enabled else 0
            
            # Проверяем, существует ли уже прокси для этого аккаунта
            existing_proxy = self.proxy_manager.get_proxy(account_id)
            
            if existing_proxy:
                # Обновляем существующий прокси
                self.proxy_manager.update_proxy(
                    account_id,
                    proxy_type=proxy_type,
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    rotation_enabled=1 if rotation_enabled else 0,
                    rotation_interval=rotation_interval
                )
                self.log_message(f"✅ Прокси обновлён для аккаунта {account_id}")
            else:
                # Добавляем новый прокси
                self.proxy_manager.add_proxy(
                    account_id=account_id,
                    proxy_type=proxy_type,
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    rotation_interval=rotation_interval
                )
                self.log_message(f"✅ Прокси добавлен для аккаунта {account_id}")
            
            # Обновляем таблицу
            self.load_proxies()
            
            logger.info(f"Прокси сохранён для аккаунта {account_id}")
            
        except ValueError as e:
            error_msg = f"Ошибка валидации: {str(e)}"
            logger.error(error_msg)
            QMessageBox.warning(self, "Ошибка валидации", error_msg)
            self.log_message(f"❌ {error_msg}")
        except Exception as e:
            error_msg = f"Ошибка сохранения прокси: {str(e)}"
            logger.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "Ошибка", error_msg)
            self.log_message(f"❌ {error_msg}")
    
    def delete_selected_proxy(self):
        """Удаляет прокси для выбранного аккаунта"""
        try:
            if self.current_account_id is None:
                QMessageBox.warning(self, "Ошибка", "Выберите аккаунт")
                return
            
            account_id = self.current_account_id
            
            # Подтверждение удаления
            reply = QMessageBox.question(
                self,
                "Подтверждение удаления",
                f"Вы уверены, что хотите удалить прокси для аккаунта {account_id}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                success = self.proxy_manager.delete_proxy(account_id)
                if success:
                    self.log_message(f"✅ Прокси удалён для аккаунта {account_id}")
                    self.clear_fields()
                    self.current_account_id = None
                    self.account_combo.setCurrentIndex(0)
                    self.load_proxies()
                else:
                    self.log_message(f"⚠️ Прокси для аккаунта {account_id} не найден")
            
        except Exception as e:
            error_msg = f"Ошибка удаления прокси: {str(e)}"
            logger.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "Ошибка", error_msg)
            self.log_message(f"❌ {error_msg}")
    
    def test_proxy(self):
        """Тестирует прокси (placeholder)"""
        try:
            if not self.validate_fields():
                return
            
            proxy_type = self.proxy_type_combo.currentText().lower()
            host = self.host_input.text().strip()
            port = self.port_spinbox.value()
            username = self.username_input.text().strip() or None
            password = self.password_input.text().strip() or None
            
            # Формируем URL прокси
            proxy_url = self.proxy_manager.format_proxy_url(
                proxy_type=proxy_type,
                host=host,
                port=port,
                username=username,
                password=password
            )
            
            self.log_message(f"🧪 Тестирование прокси: {proxy_url}")
            
            # Тестируем прокси
            result = self.proxy_manager.test_proxy(proxy_url)
            
            if result['success']:
                self.log_message(f"✅ Прокси работает! Время отклика: {result['response_time']} сек")
                QMessageBox.information(self, "Успех", f"Прокси работает!\nВремя отклика: {result['response_time']} сек")
            else:
                error_msg = result.get('error', 'Неизвестная ошибка')
                self.log_message(f"❌ Прокси не работает: {error_msg}")
                QMessageBox.warning(self, "Ошибка", f"Прокси не работает:\n{error_msg}")
            
            logger.info(f"Тестирование прокси завершено: {result}")
            
        except Exception as e:
            error_msg = f"Ошибка тестирования прокси: {str(e)}"
            logger.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "Ошибка", error_msg)
            self.log_message(f"❌ {error_msg}")
    
    def log_message(self, message: str):
        """
        Добавляет сообщение в лог
        
        Args:
            message: Текст сообщения
        """
        self.logs_text.append(message)
        # Прокручиваем вниз
        cursor = self.logs_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.logs_text.setTextCursor(cursor)

