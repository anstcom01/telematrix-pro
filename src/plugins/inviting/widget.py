"""
Виджет плагина "Инвайтинг" для приглашения пользователей в чаты Telegram
"""

import logging
import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QSpinBox, QPushButton, QTextEdit, QLabel, QGroupBox,
    QListWidget, QListWidgetItem, QFileDialog, QDialog,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from src.core.account_manager import AccountManager
from src.core.database import Database
from src.core.async_manager import AsyncManager
from src.core.inviter import Inviter

logger = logging.getLogger(__name__)


class LogHandler(logging.Handler):
    """Обработчик логов для отправки в UI через сигнал"""
    
    def __init__(self, log_signal):
        super().__init__()
        self.log_signal = log_signal
    
    def emit(self, record):
        """Отправляет лог через сигнал"""
        try:
            msg = self.format(record)
            self.log_signal.emit(msg)
        except Exception:
            pass


class InvitingThread(QThread):
    """Поток для выполнения инвайтинга в фоне"""
    
    # Сигналы для общения с UI
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int, int, int)  # success, error, skipped, total
    finished_signal = pyqtSignal(dict)  # статистика
    error_signal = pyqtSignal(str)
    
    def __init__(self, inviter, phone, chat_link, user_list, delay):
        """
        Инициализация потока инвайтинга
        
        Args:
            inviter: Экземпляр Inviter
            phone: Номер телефона аккаунта
            chat_link: Ссылка на чат
            user_list: Список пользователей для инвайта
            delay: Задержка между инвайтами в секундах
        """
        super().__init__()
        self.inviter = inviter
        self.phone = phone
        self.chat_link = chat_link
        self.user_list = user_list
        self.delay = delay
        self._stop_requested = False
        self.log_handler = None
    
    def stop(self):
        """Запрашивает остановку потока"""
        self._stop_requested = True
    
    def run(self):
        """Запуск инвайтинга в потоке"""
        try:
            # Настраиваем перехват логов из Inviter
            inviter_logger = logging.getLogger('src.core.inviter')
            self.log_handler = LogHandler(self.log_signal)
            self.log_handler.setFormatter(logging.Formatter('%(message)s'))
            inviter_logger.addHandler(self.log_handler)
            inviter_logger.setLevel(logging.INFO)
            
            # Создаём новый event loop для потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Запускаем инвайтинг
            stats = loop.run_until_complete(
                self.inviter.invite_users(
                    phone=self.phone,
                    chat_link=self.chat_link,
                    user_list=self.user_list,
                    delay=self.delay
                )
            )
            
            # Отправляем результаты
            self.finished_signal.emit(stats)
            
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            # Удаляем обработчик логов
            if self.log_handler:
                inviter_logger = logging.getLogger('src.core.inviter')
                inviter_logger.removeHandler(self.log_handler)
            loop.close()


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
        self.async_manager = AsyncManager(account_manager, database)
        self.inviter = Inviter(self.async_manager, database)
        self.is_running = False  # Флаг для отслеживания состояния инвайтинга
        self.selected_accounts = []  # Список выбранных аккаунтов
        self.success_count = 0  # Счётчик успешно добавленных
        self.error_count = 0  # Счётчик ошибок
        self.skipped_count = 0  # Счётчик пропущенных
        self.inviting_thread = None  # Поток для инвайтинга
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
        
        # Задержка между инвайтами
        delay_label = QLabel("Задержка между инвайтами (сек):")
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setMinimum(1)
        self.delay_spinbox.setMaximum(3600)
        self.delay_spinbox.setValue(60)
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(delay_label)
        delay_layout.addWidget(self.delay_spinbox)
        delay_layout.addStretch()
        settings_layout.addLayout(delay_layout)
        
        # Кнопка загрузки распарсенных пользователей
        self.load_parsed_button = QPushButton("📊 Загрузить из БД")
        self.load_parsed_button.clicked.connect(self.load_parsed_users)
        settings_layout.addWidget(self.load_parsed_button)
        
        # Кнопка выбора аккаунтов
        self.select_accounts_button = QPushButton("👥 Выбрать аккаунты")
        self.select_accounts_button.clicked.connect(self.select_accounts_dialog)
        settings_layout.addWidget(self.select_accounts_button)
        
        # Метка с количеством выбранных аккаунтов
        self.accounts_count_label = QLabel("Выбрано аккаунтов: 0")
        settings_layout.addWidget(self.accounts_count_label)
        
        settings_layout.addStretch()
        
        # Кнопки запуска и остановки
        buttons_row = QHBoxLayout()
        self.start_button = QPushButton("▶ Запустить добавление")
        self.start_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.start_button.clicked.connect(self.start_inviting)
        self.stop_button = QPushButton("⏹ Остановить")
        self.stop_button.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_inviting)
        buttons_row.addWidget(self.start_button)
        buttons_row.addWidget(self.stop_button)
        settings_layout.addLayout(buttons_row)
        
        settings_group.setLayout(settings_layout)
        
        # ПРАВАЯ КОЛОНКА "Действия программы"
        actions_group = QGroupBox("Действия программы")
        actions_layout = QVBoxLayout()
        
        # QTextEdit для логов (readonly)
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        actions_layout.addWidget(self.logs_text)
        
        # Метки со статистикой
        stats_layout = QVBoxLayout()
        self.success_label = QLabel("Успешно добавлено: 0")
        self.success_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        self.error_label = QLabel("Ошибок: 0")
        self.error_label.setStyleSheet("font-weight: bold; color: #f44336;")
        self.skipped_label = QLabel("Пропущено: 0")
        self.skipped_label.setStyleSheet("font-weight: bold; color: #ff9800;")
        stats_layout.addWidget(self.success_label)
        stats_layout.addWidget(self.error_label)
        stats_layout.addWidget(self.skipped_label)
        actions_layout.addLayout(stats_layout)
        
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
                    # Если строка не начинается с @, добавляем @
                    if not line.startswith('@') and not line.isdigit() and not line.startswith('+'):
                        line = f"@{line}"
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
    
    def load_parsed_users(self):
        """Загружает распарсенных пользователей из БД таблица parsed_users"""
        try:
            # Получаем всех распарсенных пользователей из БД
            query = "SELECT DISTINCT username FROM parsed_users WHERE username IS NOT NULL AND username != ''"
            rows = self.database.fetch_all(query)
            
            if not rows:
                self.log_message("⚠️ В базе данных нет распарсенных пользователей")
                return
            
            # Формируем список username в формате @username
            users_list = []
            for row in rows:
                username = row['username']
                if username:
                    # Убеждаемся, что username начинается с @
                    if not username.startswith('@'):
                        username = f"@{username}"
                    users_list.append(username)
            
            # Добавляем в QTextEdit (добавляем к существующему содержимому)
            current_text = self.users_text.toPlainText()
            if current_text:
                new_text = current_text + "\n" + "\n".join(users_list)
            else:
                new_text = "\n".join(users_list)
            
            self.users_text.setPlainText(new_text)
            
            self.log_message(f"✅ Загружено из БД: {len(users_list)} пользователей")
            logger.info(f"Загружено распарсенных пользователей из БД: {len(users_list)}")
            
        except Exception as e:
            error_msg = f"Ошибка загрузки из БД: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_message(f"❌ {error_msg}")
    
    def parse_users_list(self):
        """
        Парсит список пользователей из QTextEdit
        
        Returns:
            Список username или user_id (str или int)
        """
        text = self.users_text.toPlainText()
        lines = text.split('\n')
        
        users = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Если это число - это user_id
            if line.isdigit():
                users.append(int(line))
            else:
                # Иначе это username (убираем @ если есть, Inviter сам добавит)
                if line.startswith('@'):
                    users.append(line[1:])
                else:
                    users.append(line)
        
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
    
    def update_stats(self, success: int = None, error: int = None, skipped: int = None):
        """
        Обновляет статистику инвайтинга
        
        Args:
            success: Количество успешных инвайтов
            error: Количество ошибок
            skipped: Количество пропущенных
        """
        if success is not None:
            self.success_count = success
        if error is not None:
            self.error_count = error
        if skipped is not None:
            self.skipped_count = skipped
        
        self.success_label.setText(f"Успешно добавлено: {self.success_count}")
        self.error_label.setText(f"Ошибок: {self.error_count}")
        self.skipped_label.setText(f"Пропущено: {self.skipped_count}")
    
    def start_inviting(self):
        """Запускает процесс инвайтинга через Inviter в отдельном потоке"""
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
            delay = self.delay_spinbox.value()
            
            # Ограничиваем список пользователей до максимума с аккаунта
            users_to_invite = users[:max_per_account]
            
            # Устанавливаем флаг запуска
            self.is_running = True
            
            # Обновляем UI
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.users_text.setEnabled(False)
            self.target_chat_input.setEnabled(False)
            self.max_per_account_spinbox.setEnabled(False)
            self.delay_spinbox.setEnabled(False)
            self.select_accounts_button.setEnabled(False)
            self.load_file_button.setEnabled(False)
            self.load_parsed_button.setEnabled(False)
            
            # Сбрасываем статистику
            self.update_stats(success=0, error=0, skipped=0)
            
            # Логируем начало инвайтинга
            self.log_message("=" * 50)
            self.log_message("➕ Инвайтинг запущен...")
            self.log_message(f"Аккаунт: {self.selected_accounts[0]}")
            self.log_message(f"Целевая группа: {target_chat}")
            self.log_message(f"Пользователей для инвайта: {len(users_to_invite)}")
            self.log_message(f"Задержка между инвайтами: {delay} сек")
            self.log_message("=" * 50)
            
            # Создаём поток для инвайтинга
            self.inviting_thread = InvitingThread(
                inviter=self.inviter,
                phone=self.selected_accounts[0],  # Используем первый выбранный аккаунт
                chat_link=target_chat,
                user_list=users_to_invite,
                delay=delay
            )
            
            # Подключаем сигналы
            self.inviting_thread.log_signal.connect(self.log_message)
            self.inviting_thread.progress_signal.connect(self.on_progress)
            self.inviting_thread.finished_signal.connect(self.on_finished)
            self.inviting_thread.error_signal.connect(self.on_error)
            
            # Запускаем поток
            self.inviting_thread.start()
            
            logger.info(f"Инвайтинг запущен: аккаунт={self.selected_accounts[0]}, чат={target_chat}, пользователей={len(users_to_invite)}")
            
        except Exception as e:
            error_msg = f"Ошибка запуска инвайтинга: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_message(f"❌ {error_msg}")
            
            # Разблокируем UI при ошибке
            self._unlock_ui()
    
    def stop_inviting(self):
        """Останавливает процесс инвайтинга"""
        try:
            if self.inviting_thread and self.inviting_thread.isRunning():
                self.inviting_thread.stop()
                self.inviting_thread.terminate()
                self.inviting_thread.wait()
                self.log_message("⏹ Инвайтинг остановлен пользователем")
                logger.info("Инвайтинг остановлен пользователем")
            
            self._unlock_ui()
            
        except Exception as e:
            error_msg = f"Ошибка остановки инвайтинга: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_message(f"❌ {error_msg}")
    
    def on_progress(self, success: int, error: int, skipped: int, total: int):
        """Обработчик сигнала прогресса"""
        self.update_stats(success=success, error=error, skipped=skipped)
        self.log_message(f"Прогресс: Успешно: {success}, Ошибок: {error}, Пропущено: {skipped} из {total}")
    
    def on_finished(self, stats: dict):
        """Обработчик завершения инвайтинга"""
        try:
            success = stats.get('success', 0)
            error = stats.get('error', 0)
            skipped = stats.get('skipped', 0)
            
            self.update_stats(success=success, error=error, skipped=skipped)
            
            self.log_message("=" * 50)
            self.log_message("✅ Инвайтинг завершён!")
            self.log_message(f"Успешно добавлено: {success}")
            self.log_message(f"Ошибок: {error}")
            self.log_message(f"Пропущено: {skipped}")
            self.log_message("=" * 50)
            
            logger.info(f"Инвайтинг завершён: {stats}")
            
        except Exception as e:
            logger.error(f"Ошибка обработки завершения: {e}", exc_info=True)
        finally:
            self._unlock_ui()
    
    def on_error(self, error_msg: str):
        """Обработчик ошибки инвайтинга"""
        self.log_message(f"❌ Ошибка инвайтинга: {error_msg}")
        logger.error(f"Ошибка в потоке инвайтинга: {error_msg}")
        self._unlock_ui()
    
    def _unlock_ui(self):
        """Разблокирует UI элементы"""
        self.is_running = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.users_text.setEnabled(True)
        self.target_chat_input.setEnabled(True)
        self.max_per_account_spinbox.setEnabled(True)
        self.delay_spinbox.setEnabled(True)
        self.select_accounts_button.setEnabled(True)
        self.load_file_button.setEnabled(True)
        self.load_parsed_button.setEnabled(True)
