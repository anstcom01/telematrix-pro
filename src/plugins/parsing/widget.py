"""
Виджет плагина "Парсинг" для парсинга участников из чатов Telegram
"""

import logging
import asyncio
import csv
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit,
    QSpinBox, QCheckBox, QPushButton, QTextEdit, QLabel, QGroupBox,
    QRadioButton, QButtonGroup, QListWidget, QListWidgetItem, QFileDialog,
    QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem, QApplication,
    QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import QHeaderView

from src.core.account_manager import AccountManager
from src.core.database import Database
from src.core.parser import Parser
from src.core.async_manager import AsyncManager

logger = logging.getLogger(__name__)


class ParsingThread(QThread):
    """Поток для выполнения парсинга в фоне"""
    
    # Сигналы для общения с UI
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)  # parsed, total
    finished_signal = pyqtSignal(list)  # результаты
    error_signal = pyqtSignal(str)
    
    def __init__(self, parser, phone, chat_link, limit, filters):
        """
        Инициализация потока парсинга
        
        Args:
            parser: Экземпляр Parser
            phone: Номер телефона аккаунта
            chat_link: Ссылка на чат
            limit: Лимит участников
            filters: Словарь с фильтрами
        """
        super().__init__()
        self.parser = parser
        self.phone = phone
        self.chat_link = chat_link
        self.limit = limit
        self.filters = filters
    
    def run(self):
        """Запуск парсинга в потоке"""
        try:
            # Создаём новый event loop для потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Запускаем парсинг
            results = loop.run_until_complete(
                self.parser.parse_chat_participants(
                    self.phone,
                    self.chat_link,
                    self.limit,
                    self.filters
                )
            )
            
            # Отправляем результаты
            self.finished_signal.emit(results)
            
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            loop.close()


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
        self.parser = None  # Будет инициализирован при первом использовании
        self.parsed_results = []  # Список распарсенных результатов
        self.is_running = False  # Флаг состояния парсинга
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
        self.save_button.clicked.connect(self.save_results_to_csv)
        settings_layout.addWidget(self.save_button)
        
        settings_group.setLayout(settings_layout)
        
        # ПРАВАЯ КОЛОНКА "Действия программы"
        actions_group = QGroupBox("Действия программы")
        actions_layout = QVBoxLayout()
        
        # QTextEdit для логов (readonly)
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setMaximumHeight(200)
        actions_layout.addWidget(self.logs_text)
        
        # Таблица результатов
        results_label = QLabel("Результаты парсинга:")
        actions_layout.addWidget(results_label)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels(["Username", "ID", "Имя", "Телефон", "Бот?", "Premium?"])
        
        # Настройка ширины колонок
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Username
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Имя
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Телефон
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Бот?
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Premium?
        
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        actions_layout.addWidget(self.results_table)
        
        # Метка с количеством результатов
        self.results_count_label = QLabel("Найдено: 0 участников")
        actions_layout.addWidget(self.results_count_label)
        
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
    
    def _get_parser(self):
        """Получает или создаёт экземпляр Parser"""
        if self.parser is None:
            # Находим главное окно для получения async_manager
            main_window = None
            for widget in QApplication.topLevelWidgets():
                if hasattr(widget, 'async_manager'):
                    main_window = widget
                    break
            
            if main_window and hasattr(main_window, 'async_manager'):
                from src.core.parser import Parser
                self.parser = Parser(main_window.async_manager, self.database)
                logger.info("Parser создан для ParsingWidget")
            else:
                logger.error("Не удалось найти async_manager для создания Parser")
                return None
        
        return self.parser
    
    def start_parsing(self):
        """Запускает процесс парсинга через Parser"""
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
            
            # Получаем parser
            parser = self._get_parser()
            if not parser:
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    "Не удалось инициализировать Parser. Проверьте подключение к базе данных."
                )
                return
            
            # Получаем фильтры из UI
            filters = {
                'only_usernames': self.parse_username_radio.isChecked(),  # Только с username
                'only_active': self.status_week_checkbox.isChecked() or self.status_recent_checkbox.isChecked(),
                'exclude_bots': self.status_antibot_checkbox.isChecked(),
                'exclude_premium': False  # По умолчанию не исключаем premium
            }
            
            # Лимит из настроек (используем значение по умолчанию 100, можно добавить SpinBox)
            limit = 100
            
            # Устанавливаем флаг запуска
            self.is_running = True
            
            # Обновляем UI
            self.start_button.setEnabled(False)
            self.chats_text.setEnabled(False)
            self.select_accounts_button.setEnabled(False)
            self.load_button.setEnabled(False)
            
            # Очищаем предыдущие результаты
            self.parsed_results = []
            self.results_table.setRowCount(0)
            
            # Логируем начало парсинга
            self.log_message("=" * 50)
            self.log_message("🔍 Парсинг запущен...")
            self.log_message(f"Аккаунт: {self.selected_accounts[0]}")
            self.log_message(f"Чатов в списке: {len(chats_list)}")
            self.log_message(f"Лимит: {limit}")
            self.log_message(f"Фильтры: только с username={filters['only_usernames']}, "
                           f"только активные={filters['only_active']}, "
                           f"исключить ботов={filters['exclude_bots']}")
            self.log_message("=" * 50)
            
            # Запускаем парсинг для первого чата (можно расширить для множественных чатов)
            chat_link = chats_list[0]
            phone = self.selected_accounts[0]
            
            # Создаём поток для парсинга
            self.parsing_thread = ParsingThread(parser, phone, chat_link, limit, filters)
            self.parsing_thread.log_signal.connect(self.log_message)
            self.parsing_thread.progress_signal.connect(self._on_progress)
            self.parsing_thread.finished_signal.connect(self._on_parsing_finished)
            self.parsing_thread.error_signal.connect(self._on_parsing_error)
            self.parsing_thread.start()
            
            logger.info(f"Парсинг запущен: аккаунт={phone}, чат={chat_link}, лимит={limit}")
            
        except Exception as e:
            error_msg = f"Ошибка запуска парсинга: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_message(f"❌ {error_msg}")
            
            # Разблокируем UI при ошибке
            self._reset_ui()
    
    def _on_progress(self, parsed: int, total: int):
        """Обработчик сигнала прогресса парсинга"""
        self.log_message(f"Распарсено {parsed}/{total} участников")
    
    def _on_parsing_finished(self, results: list):
        """Обработчик завершения парсинга"""
        try:
            self.parsed_results = results
            
            if results:
                self.log_message(f"✅ Парсинг завершён! Найдено участников: {len(results)}")
                self.load_results(results)
            else:
                self.log_message("⚠️ Парсинг завершён, но участники не найдены")
            
            logger.info(f"Парсинг завершён. Найдено участников: {len(results)}")
            
        except Exception as e:
            logger.error(f"Ошибка обработки результатов парсинга: {e}", exc_info=True)
            self.log_message(f"❌ Ошибка обработки результатов: {str(e)}")
        finally:
            self._reset_ui()
    
    def _on_parsing_error(self, error_msg: str):
        """Обработчик ошибки парсинга"""
        logger.error(f"Ошибка парсинга: {error_msg}")
        self.log_message(f"❌ Ошибка парсинга: {error_msg}")
        
        # Показываем сообщение об ошибке
        QMessageBox.critical(
            self,
            "Ошибка парсинга",
            f"Произошла ошибка при парсинге:\n{error_msg}"
        )
        
        self._reset_ui()
    
    def _reset_ui(self):
        """Сбрасывает состояние UI после парсинга"""
        self.is_running = False
        self.start_button.setEnabled(True)
        self.chats_text.setEnabled(True)
        self.select_accounts_button.setEnabled(True)
        self.load_button.setEnabled(True)
    
    def load_results(self, results: list):
        """
        Загружает результаты парсинга в таблицу
        
        Args:
            results: Список словарей с данными участников
        """
        try:
            # Очищаем таблицу
            self.results_table.setRowCount(0)
            
            # Заполняем таблицу
            for user in results:
                row = self.results_table.rowCount()
                self.results_table.insertRow(row)
                
                # Username
                username = user.get('username', 'N/A')
                if username and username != 'N/A':
                    username = f"@{username}"
                username_item = QTableWidgetItem(username)
                username_item.setFlags(username_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.results_table.setItem(row, 0, username_item)
                
                # ID
                id_item = QTableWidgetItem(str(user.get('id', 'N/A')))
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.results_table.setItem(row, 1, id_item)
                
                # Имя
                first_name = user.get('first_name', '')
                last_name = user.get('last_name', '')
                full_name = f"{first_name} {last_name}".strip() or 'N/A'
                name_item = QTableWidgetItem(full_name)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.results_table.setItem(row, 2, name_item)
                
                # Телефон
                phone = user.get('phone', 'N/A')
                phone_item = QTableWidgetItem(str(phone) if phone else 'N/A')
                phone_item.setFlags(phone_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.results_table.setItem(row, 3, phone_item)
                
                # Бот?
                is_bot = user.get('is_bot', False)
                bot_item = QTableWidgetItem("Да" if is_bot else "Нет")
                bot_item.setFlags(bot_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.results_table.setItem(row, 4, bot_item)
                
                # Premium?
                is_premium = user.get('is_premium', False)
                premium_item = QTableWidgetItem("Да" if is_premium else "Нет")
                premium_item.setFlags(premium_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.results_table.setItem(row, 5, premium_item)
            
            # Обновляем метку с количеством
            self.results_count_label.setText(f"Найдено: {len(results)} участников")
            
            logger.info(f"Результаты загружены в таблицу: {len(results)} участников")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки результатов в таблицу: {e}", exc_info=True)
            self.log_message(f"❌ Ошибка загрузки результатов: {str(e)}")
    
    def save_results_to_csv(self):
        """Сохраняет результаты парсинга в CSV файл"""
        try:
            if not self.parsed_results:
                QMessageBox.warning(
                    self,
                    "Нет данных",
                    "Нет результатов для сохранения. Сначала выполните парсинг."
                )
                return
            
            # Открываем диалог сохранения файла
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить результаты в CSV",
                "",
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if not file_path:
                return
            
            # Сохраняем в CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Заголовки
                writer.writerow(['Username', 'ID', 'Имя', 'Фамилия', 'Телефон', 'Бот', 'Premium'])
                
                # Данные
                for user in self.parsed_results:
                    writer.writerow([
                        user.get('username', ''),
                        user.get('id', ''),
                        user.get('first_name', ''),
                        user.get('last_name', ''),
                        user.get('phone', ''),
                        'Да' if user.get('is_bot', False) else 'Нет',
                        'Да' if user.get('is_premium', False) else 'Нет'
                    ])
            
            QMessageBox.information(
                self,
                "Успех",
                f"Результаты сохранены в файл:\n{file_path}"
            )
            
            self.log_message(f"✅ Результаты сохранены в CSV: {file_path}")
            logger.info(f"Результаты сохранены в CSV: {file_path}")
            
        except Exception as e:
            error_msg = f"Ошибка сохранения результатов: {str(e)}"
            logger.error(error_msg, exc_info=True)
            QMessageBox.critical(
                self,
                "Ошибка",
                error_msg
            )
