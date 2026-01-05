"""
Виджет плагина "Инвайтинг" для приглашения пользователей в чаты Telegram
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QSpinBox, QPushButton, QTextEdit, QLabel, QGroupBox,
    QListWidget, QListWidgetItem, QFileDialog, QDialog,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from src.core.account_manager import AccountManager
from src.core.database import Database

logger = logging.getLogger(__name__)


class InvitingWidget(QWidget):
    """Виджет для приглашения пользователей в чаты Telegram"""
    
    def __init__(self, account_manager: AccountManager, database: Database):
        """
        Инициализация виджета инвайтинга
        
        Args:
            account_manager: Экземпляр AccountManager для работы с аккаунтами
            database: Экземпляр Database для работы с БД
        """
        super().__init__()
        self.account_manager = account_manager
        self.database = database
        self.is_running = False  # Флаг для отслеживания состояния инвайтинга
        self.selected_accounts = []  # Список выбранных аккаунтов
        self.success_count = 0  # Счётчик успешно добавленных
        self.init_ui()
        logger.info("InvitingWidget инициализирован")
    
    @staticmethod
    def get_info():
        """
        Возвращает информацию о плагине
        
        Returns:
            Словарь с информацией о плагине
        """
        return {
            "name": "Инвайтинг",
            "icon": "➕",
            "description": "Приглашение пользователей в чаты"
        }
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        main_layout = QHBoxLayout()
        
        # ЛЕВАЯ КОЛОНКА "Настройки"
        settings_group = QGroupBox("Настройки")
        settings_layout = QVBoxLayout()
        
        # QTextEdit для ввода списка пользователей
        users_label = QLabel("Список пользователей:")
        self.users_text = QTextEdit()
        self.users_text.setPlaceholderText("@username / phones...")
        self.users_text.setMaximumHeight(150)
        settings_layout.addWidget(users_label)
        settings_layout.addWidget(self.users_text)
        
        # Кнопка загрузки из файла
        self.load_file_button = QPushButton("📁 Загрузить из файла")
        self.load_file_button.clicked.connect(self.load_from_file)
        settings_layout.addWidget(self.load_file_button)
        
        # Целевая группа
        target_label = QLabel("Целевая группа:")
        self.target_chat_input = QLineEdit()
        self.target_chat_input.setPlaceholderText("@login")
        settings_layout.addWidget(target_label)
        settings_layout.addWidget(self.target_chat_input)
        
        # Максимум с аккаунта
        max_label = QLabel("Максимум с аккаунта:")
        self.max_per_account_spinbox = QSpinBox()
        self.max_per_account_spinbox.setMinimum(1)
        self.max_per_account_spinbox.setMaximum(1000)
        self.max_per_account_spinbox.setValue(40)
        max_layout = QHBoxLayout()
        max_layout.addWidget(max_label)
        max_layout.addWidget(self.max_per_account_spinbox)
        max_layout.addStretch()
        settings_layout.addLayout(max_layout)
        
        # Кнопка выбора аккаунтов
        self.select_accounts_button = QPushButton("👥 Выбрать аккаунты")
        self.select_accounts_button.clicked.connect(self.select_accounts_dialog)
        settings_layout.addWidget(self.select_accounts_button)
        
        # Метка с количеством выбранных аккаунтов
        self.accounts_count_label = QLabel("Выбрано аккаунтов: 0")
        settings_layout.addWidget(self.accounts_count_label)
        
        settings_layout.addStretch()
        
        # Кнопка запуска (зелёная)
        self.start_button = QPushButton("Запустить добавление")
        self.start_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.start_button.clicked.connect(self.start_inviting)
        settings_layout.addWidget(self.start_button)
        
        settings_group.setLayout(settings_layout)
        
        # ПРАВАЯ КОЛОНКА "Действия программы"
        actions_group = QGroupBox("Действия программы")
        actions_layout = QVBoxLayout()
        
        # QTextEdit для логов (readonly)
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        actions_layout.addWidget(self.logs_text)
        
        # Метка с количеством успешно добавленных
        self.success_label = QLabel("Успешно добавлено: 0")
        self.success_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        actions_layout.addWidget(self.success_label)
        
        actions_group.setLayout(actions_layout)
        
        # Добавляем группы в основной layout
        main_layout.addWidget(settings_group, 40)  # Левая колонка 40%
        main_layout.addWidget(actions_group, 60)   # Правая колонка 60%
        
        self.setLayout(main_layout)
    
    def load_from_file(self):
        """Загружает пользователей из .txt файла и добавляет в QTextEdit"""
        try:
            # Открываем диалог выбора файла
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Выберите файл .txt",
                "",
                "Text Files (*.txt);;All Files (*)"
            )
            
            if not file_path:
                return
            
            # Читаем файл
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Парсим и добавляем в QTextEdit
            users_list = []
            for line in lines:
                line = line.strip()
                if line:
                    users_list.append(line)
            
            # Добавляем в QTextEdit (добавляем к существующему содержимому)
            current_text = self.users_text.toPlainText()
            if current_text:
                new_text = current_text + "\n" + "\n".join(users_list)
            else:
                new_text = "\n".join(users_list)
            
            self.users_text.setPlainText(new_text)
            
            self.log_message(f"✅ Загружено из файла: {len(users_list)} строк")
            logger.info(f"Загружено пользователей из файла: {len(users_list)}")
            
        except FileNotFoundError:
            error_msg = "Файл не найден"
            logger.error(error_msg)
            self.log_message(f"❌ {error_msg}")
        except Exception as e:
            error_msg = f"Ошибка загрузки файла: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_message(f"❌ {error_msg}")
    
    def parse_users_list(self):
        """
        Парсит список пользователей из QTextEdit
        
        Returns:
            Список словарей с данными пользователей: [{"value": str, "type": "Username"/"ID"/"Phone"}]
        """
        text = self.users_text.toPlainText()
        lines = text.split('\n')
        
        users = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Определяем тип
            if line.startswith('@'):
                # Username начинается с @
                username = line[1:] if len(line) > 1 else ""
                if username:
                    users.append({"value": line, "type": "Username"})
            elif line.isdigit():
                # Только цифры - это user_id
                users.append({"value": line, "type": "ID"})
            elif line.startswith('+') and line[1:].replace(' ', '').isdigit():
                # Номер телефона начинается с +
                users.append({"value": line, "type": "Phone"})
            elif any(c.isdigit() for c in line) and len(line) >= 10:
                # Длинная строка с цифрами - возможно номер телефона
                users.append({"value": line, "type": "Phone"})
            else:
                # Текст без @ - считаем username
                users.append({"value": f"@{line}" if not line.startswith('@') else line, "type": "Username"})
        
        return users
    
    def select_accounts_dialog(self):
        """Открывает диалог выбора аккаунтов с QListWidget множественного выбора"""
        try:
            # Получаем список всех аккаунтов
            accounts = self.account_manager.get_all_accounts()
            
            if not accounts:
                self.log_message("⚠️ Аккаунты не найдены. Добавьте аккаунт в плагине 'Аккаунты'")
                return
            
            # Создаём диалог
            dialog = QDialog(self)
            dialog.setWindowTitle("Выбор аккаунтов")
            dialog.setModal(True)
            dialog.resize(400, 300)
            
            layout = QVBoxLayout()
            
            # QListWidget с множественным выбором
            accounts_list = QListWidget()
            accounts_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            
            # Загружаем аккаунты
            for account in accounts:
                display_text = f"{account['phone']} (ID: {account['id']})"
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, account['phone'])
                
                # Выделяем уже выбранные аккаунты
                if account['phone'] in self.selected_accounts:
                    item.setSelected(True)
                
                accounts_list.addItem(item)
            
            layout.addWidget(QLabel("Выберите аккаунты (Ctrl+Click для множественного выбора):"))
            layout.addWidget(accounts_list)
            
            # Кнопки диалога
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            
            dialog.setLayout(layout)
            
            # Показываем диалог
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Получаем выбранные аккаунты
                selected_items = accounts_list.selectedItems()
                self.selected_accounts = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
                
                # Обновляем метку
                self.accounts_count_label.setText(f"Выбрано аккаунтов: {len(self.selected_accounts)}")
                
                self.log_message(f"✅ Выбрано аккаунтов: {len(self.selected_accounts)}")
                logger.info(f"Выбрано аккаунтов: {len(self.selected_accounts)}")
            
        except Exception as e:
            error_msg = f"Ошибка выбора аккаунтов: {str(e)}"
            logger.error(error_msg, exc_info=True)
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
    
    def update_success_count(self, count: int = None):
        """
        Обновляет счётчик успешно добавленных
        
        Args:
            count: Новое значение счётчика (если None, увеличивает на 1)
        """
        if count is not None:
            self.success_count = count
        else:
            self.success_count += 1
        
        self.success_label.setText(f"Успешно добавлено: {self.success_count}")
    
    def start_inviting(self):
        """Запускает процесс инвайтинга (placeholder)"""
        try:
            # Проверка выбранных аккаунтов
            if not self.selected_accounts:
                self.log_message("❌ Не выбран ни один аккаунт. Нажмите '👥 Выбрать аккаунты'")
                return
            
            # Проверка целевой группы
            target_chat = self.target_chat_input.text().strip()
            if not target_chat:
                self.log_message("❌ Введите целевую группу")
                return
            
            # Парсим список пользователей
            users = self.parse_users_list()
            if not users:
                self.log_message("❌ Список пользователей пуст. Введите пользователей или загрузите из файла")
                return
            
            # Получаем параметры
            max_per_account = self.max_per_account_spinbox.value()
            
            # Устанавливаем флаг запуска
            self.is_running = True
            
            # Обновляем UI
            self.start_button.setEnabled(False)
            self.users_text.setEnabled(False)
            self.target_chat_input.setEnabled(False)
            self.max_per_account_spinbox.setEnabled(False)
            self.select_accounts_button.setEnabled(False)
            self.load_file_button.setEnabled(False)
            
            # Сбрасываем счётчик успеха
            self.update_success_count(0)
            
            # Логируем начало инвайтинга
            self.log_message("=" * 50)
            self.log_message("➕ Инвайтинг запущен...")
            self.log_message(f"Запуск инвайтинга с {len(self.selected_accounts)} аккаунтами:")
            for i, phone in enumerate(self.selected_accounts, 1):
                self.log_message(f"  {i}. {phone}")
            self.log_message(f"Целевая группа: {target_chat}")
            self.log_message(f"Максимум с аккаунта: {max_per_account}")
            self.log_message(f"Пользователей в списке: {len(users)}")
            self.log_message("=" * 50)
            
            # Парсим типы пользователей
            username_count = sum(1 for u in users if u['type'] == 'Username')
            id_count = sum(1 for u in users if u['type'] == 'ID')
            phone_count = sum(1 for u in users if u['type'] == 'Phone')
            
            self.log_message(f"Распределение по типам:")
            self.log_message(f"  Username: {username_count}")
            self.log_message(f"  ID: {id_count}")
            self.log_message(f"  Phone: {phone_count}")
            
            # TODO: Здесь будет реальная логика инвайтинга через Telethon
            # Пока placeholder
            self.log_message("⚠️ Функция инвайтинга в разработке...")
            self.log_message("Реальная логика инвайтинга будет добавлена позже")
            
            logger.info(f"Инвайтинг запущен (placeholder): аккаунты={self.selected_accounts}, чат={target_chat}, пользователей={len(users)}")
            
            # Разблокируем UI после завершения (в реальной реализации это будет в отдельном потоке)
            self.is_running = False
            self.start_button.setEnabled(True)
            self.users_text.setEnabled(True)
            self.target_chat_input.setEnabled(True)
            self.max_per_account_spinbox.setEnabled(True)
            self.select_accounts_button.setEnabled(True)
            self.load_file_button.setEnabled(True)
            
        except Exception as e:
            error_msg = f"Ошибка запуска инвайтинга: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_message(f"❌ {error_msg}")
            
            # Разблокируем UI при ошибке
            self.is_running = False
            self.start_button.setEnabled(True)
            self.users_text.setEnabled(True)
            self.target_chat_input.setEnabled(True)
            self.max_per_account_spinbox.setEnabled(True)
            self.select_accounts_button.setEnabled(True)
            self.load_file_button.setEnabled(True)
