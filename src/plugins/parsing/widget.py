"""
Виджет плагина "Парсинг" для парсинга участников из чатов Telegram
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit,
    QSpinBox, QCheckBox, QPushButton, QTextEdit, QLabel, QGroupBox,
    QRadioButton, QButtonGroup, QListWidget, QListWidgetItem, QFileDialog,
    QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt

from src.core.account_manager import AccountManager
from src.core.database import Database

logger = logging.getLogger(__name__)


class ParsingWidget(QWidget):
    """Виджет для парсинга участников из чатов Telegram"""
    
    def __init__(self, account_manager: AccountManager, database: Database):
        """
        Инициализация виджета парсинга
        
        Args:
            account_manager: Экземпляр AccountManager для работы с аккаунтами
            database: Экземпляр Database (для совместимости с PluginSystem)
        """
        super().__init__()
        self.account_manager = account_manager
        self.database = database
        self.selected_accounts = []  # Список выбранных аккаунтов
        self.init_ui()
        logger.info("ParsingWidget инициализирован")
    
    @staticmethod
    def get_info():
        """
        Возвращает информацию о плагине
        
        Returns:
            Словарь с информацией о плагине
        """
        return {
            "name": "Парсинг",
            "icon": "🔍",
            "description": "Парсинг участников из чатов"
        }
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        main_layout = QHBoxLayout()
        
        # ЛЕВАЯ КОЛОНКА "Настройки парсинга"
        settings_group = QGroupBox("Настройки парсинга")
        settings_layout = QVBoxLayout()
        
        # QTextEdit для ввода списка чатов
        chats_label = QLabel("Список чатов:")
        self.chats_text = QTextEdit()
        self.chats_text.setPlaceholderText("@username...")
        self.chats_text.setMaximumHeight(100)
        settings_layout.addWidget(chats_label)
        settings_layout.addWidget(self.chats_text)
        
        # Ряд кнопок
        buttons_row = QHBoxLayout()
        self.search_button = QPushButton("🔍 Поиск")
        self.load_button = QPushButton("📁 Загрузить")
        self.load_button.clicked.connect(self.load_chats_from_file)
        self.refresh_button = QPushButton("↻ Обновить")
        buttons_row.addWidget(self.search_button)
        buttons_row.addWidget(self.load_button)
        buttons_row.addWidget(self.refresh_button)
        settings_layout.addLayout(buttons_row)
        
        # QComboBox "Статус"
        status_label = QLabel("Статус:")
        self.status_combo = QComboBox()
        self.status_combo.addItems([
            "Фильтр по гендеру",
            "Язык аудитории",
            "Администраторы"
        ])
        settings_layout.addWidget(status_label)
        settings_layout.addWidget(self.status_combo)
        
        # QGroupBox "Парсить:"
        parse_group = QGroupBox("Парсить:")
        parse_layout = QVBoxLayout()
        
        parse_button_group = QButtonGroup()
        self.parse_id_no_username_radio = QRadioButton("ID без username")
        self.parse_id_with_username_radio = QRadioButton("ID + ID username")
        self.parse_username_radio = QRadioButton("@Username")
        self.parse_username_radio.setChecked(True)  # Выбран по умолчанию
        self.parse_phones_radio = QRadioButton("Телефоны")
        
        parse_button_group.addButton(self.parse_id_no_username_radio)
        parse_button_group.addButton(self.parse_id_with_username_radio)
        parse_button_group.addButton(self.parse_username_radio)
        parse_button_group.addButton(self.parse_phones_radio)
        
        parse_layout.addWidget(self.parse_id_no_username_radio)
        parse_layout.addWidget(self.parse_id_with_username_radio)
        parse_layout.addWidget(self.parse_username_radio)
        parse_layout.addWidget(self.parse_phones_radio)
        
        parse_group.setLayout(parse_layout)
        settings_layout.addWidget(parse_group)
        
        # QGroupBox "Скрытые статусы:"
        statuses_group = QGroupBox("Скрытые статусы:")
        statuses_layout = QVBoxLayout()
        
        self.status_online_checkbox = QCheckBox("Сейчас онлайн")
        self.status_month_checkbox = QCheckBox("Заходил в этом месяце")
        self.status_week_checkbox = QCheckBox("Заходил на этой неделе")
        self.status_recent_checkbox = QCheckBox("Был недавно")
        self.status_long_ago_checkbox = QCheckBox("Не заходил давно")
        self.status_all_checkbox = QCheckBox("Всех (без фильтра)")
        self.status_antibot_checkbox = QCheckBox("АнтиБот")
        
        statuses_layout.addWidget(self.status_online_checkbox)
        statuses_layout.addWidget(self.status_month_checkbox)
        statuses_layout.addWidget(self.status_week_checkbox)
        statuses_layout.addWidget(self.status_recent_checkbox)
        statuses_layout.addWidget(self.status_long_ago_checkbox)
        statuses_layout.addWidget(self.status_all_checkbox)
        statuses_layout.addWidget(self.status_antibot_checkbox)
        
        statuses_group.setLayout(statuses_layout)
        settings_layout.addWidget(statuses_group)
        
        # QCheckBox для Premium
        self.premium_checkbox = QCheckBox("Собрать отдельно пользователей с ⭐ Premium подпиской")
        settings_layout.addWidget(self.premium_checkbox)
        
        # QGroupBox "Время онлайна аудитории:"
        online_time_group = QGroupBox("Время онлайна аудитории:")
        online_time_layout = QHBoxLayout()
        
        self.online_from_spinbox = QSpinBox()
        self.online_from_spinbox.setMinimum(0)
        self.online_from_spinbox.setMaximum(365)
        self.online_from_spinbox.setValue(0)
        
        self.online_to_spinbox = QSpinBox()
        self.online_to_spinbox.setMinimum(0)
        self.online_to_spinbox.setMaximum(365)
        self.online_to_spinbox.setValue(3)
        
        online_time_layout.addWidget(QLabel("от"))
        online_time_layout.addWidget(self.online_from_spinbox)
        online_time_layout.addWidget(QLabel("до"))
        online_time_layout.addWidget(self.online_to_spinbox)
        online_time_layout.addWidget(QLabel("дней"))
        online_time_layout.addStretch()
        
        online_time_group.setLayout(online_time_layout)
        settings_layout.addWidget(online_time_group)
        
        settings_layout.addStretch()
        
        # Кнопка выбора аккаунтов
        self.select_accounts_button = QPushButton("👥 Выбрать аккаунты")
        self.select_accounts_button.clicked.connect(self.select_accounts_dialog)
        settings_layout.addWidget(self.select_accounts_button)
        
        # Кнопка запуска (зелёная)
        self.start_button = QPushButton("Запустить")
        self.start_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.start_button.clicked.connect(self.start_parsing)
        settings_layout.addWidget(self.start_button)
        
        # Кнопка сохранения результата
        self.save_button = QPushButton("Сохранить результат")
        settings_layout.addWidget(self.save_button)
        
        settings_group.setLayout(settings_layout)
        
        # ПРАВАЯ КОЛОНКА "Действия программы"
        actions_group = QGroupBox("Действия программы")
        actions_layout = QVBoxLayout()
        
        # QTextEdit для логов (readonly)
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        actions_layout.addWidget(self.logs_text)
        
        actions_group.setLayout(actions_layout)
        
        # Добавляем группы в основной layout
        main_layout.addWidget(settings_group, 45)  # Левая колонка 45%
        main_layout.addWidget(actions_group, 55)   # Правая колонка 55%
        
        self.setLayout(main_layout)
    
    def load_chats_from_file(self):
        """Загружает список чатов из .txt файла и добавляет в QTextEdit"""
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
            chats_list = []
            for line in lines:
                line = line.strip()
                if line:
                    chats_list.append(line)
            
            # Добавляем в QTextEdit (добавляем к существующему содержимому)
            current_text = self.chats_text.toPlainText()
            if current_text:
                new_text = current_text + "\n" + "\n".join(chats_list)
            else:
                new_text = "\n".join(chats_list)
            
            self.chats_text.setPlainText(new_text)
            
            self.log_message(f"✅ Загружено из файла: {len(chats_list)} чатов")
            logger.info(f"Загружено чатов из файла: {len(chats_list)}")
            
        except FileNotFoundError:
            error_msg = "Файл не найден"
            logger.error(error_msg)
            self.log_message(f"❌ {error_msg}")
        except Exception as e:
            error_msg = f"Ошибка загрузки файла: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_message(f"❌ {error_msg}")
    
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
    
    def start_parsing(self):
        """Запускает процесс парсинга (placeholder)"""
        try:
            # Проверка выбранных аккаунтов
            if not self.selected_accounts:
                self.log_message("❌ Не выбран ни один аккаунт. Нажмите '👥 Выбрать аккаунты'")
                return
            
            # Получаем список чатов
            chats_text = self.chats_text.toPlainText().strip()
            if not chats_text:
                self.log_message("❌ Список чатов пуст. Введите чаты или загрузите из файла")
                return
            
            chats_list = [line.strip() for line in chats_text.split('\n') if line.strip()]
            
            # Получаем все настройки
            status_filter = self.status_combo.currentText()
            
            # Определяем тип парсинга
            if self.parse_id_no_username_radio.isChecked():
                parse_type = "ID без username"
            elif self.parse_id_with_username_radio.isChecked():
                parse_type = "ID + ID username"
            elif self.parse_username_radio.isChecked():
                parse_type = "@Username"
            elif self.parse_phones_radio.isChecked():
                parse_type = "Телефоны"
            else:
                parse_type = "Не выбрано"
            
            # Получаем выбранные статусы
            selected_statuses = []
            if self.status_online_checkbox.isChecked():
                selected_statuses.append("Сейчас онлайн")
            if self.status_month_checkbox.isChecked():
                selected_statuses.append("Заходил в этом месяце")
            if self.status_week_checkbox.isChecked():
                selected_statuses.append("Заходил на этой неделе")
            if self.status_recent_checkbox.isChecked():
                selected_statuses.append("Был недавно")
            if self.status_long_ago_checkbox.isChecked():
                selected_statuses.append("Не заходил давно")
            if self.status_all_checkbox.isChecked():
                selected_statuses.append("Всех (без фильтра)")
            if self.status_antibot_checkbox.isChecked():
                selected_statuses.append("АнтиБот")
            
            premium_separate = self.premium_checkbox.isChecked()
            online_from = self.online_from_spinbox.value()
            online_to = self.online_to_spinbox.value()
            
            # Устанавливаем флаг запуска
            self.is_running = True
            
            # Обновляем UI
            self.start_button.setEnabled(False)
            self.chats_text.setEnabled(False)
            self.select_accounts_button.setEnabled(False)
            self.load_button.setEnabled(False)
            
            # Логируем начало парсинга
            self.log_message("=" * 50)
            self.log_message("🔍 Парсинг запущен...")
            self.log_message(f"Запуск парсинга с {len(self.selected_accounts)} аккаунтами:")
            for i, phone in enumerate(self.selected_accounts, 1):
                self.log_message(f"  {i}. {phone}")
            self.log_message(f"Чатов в списке: {len(chats_list)}")
            self.log_message(f"Статус фильтр: {status_filter}")
            self.log_message(f"Тип парсинга: {parse_type}")
            self.log_message(f"Выбранные статусы: {', '.join(selected_statuses) if selected_statuses else 'Нет'}")
            self.log_message(f"Premium отдельно: {'Да' if premium_separate else 'Нет'}")
            self.log_message(f"Время онлайна: от {online_from} до {online_to} дней")
            self.log_message("=" * 50)
            
            # TODO: Здесь будет реальная логика парсинга через Telethon
            # Пока placeholder
            self.log_message("⚠️ Функция парсинга в разработке...")
            self.log_message("Реальная логика парсинга будет добавлена позже")
            
            logger.info(f"Парсинг запущен (placeholder): аккаунты={self.selected_accounts}, чатов={len(chats_list)}, тип={parse_type}")
            
            # Разблокируем UI после завершения (в реальной реализации это будет в отдельном потоке)
            self.is_running = False
            self.start_button.setEnabled(True)
            self.chats_text.setEnabled(True)
            self.select_accounts_button.setEnabled(True)
            self.load_button.setEnabled(True)
            
        except Exception as e:
            error_msg = f"Ошибка запуска парсинга: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_message(f"❌ {error_msg}")
            
            # Разблокируем UI при ошибке
            self.is_running = False
            self.start_button.setEnabled(True)
            self.chats_text.setEnabled(True)
            self.select_accounts_button.setEnabled(True)
            self.load_button.setEnabled(True)
