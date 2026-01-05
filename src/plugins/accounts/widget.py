"""
Виджет плагина "Аккаунты" для управления Telegram аккаунтами
"""

import logging
import random
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QPushButton, QDialog, QFormLayout,
    QLineEdit, QMessageBox, QDialogButtonBox, QComboBox,
    QLabel, QCheckBox, QHeaderView, QFileDialog
)
from PyQt6.QtCore import Qt

from src.core.account_manager import AccountManager
from src.core.database import Database

logger = logging.getLogger(__name__)


class AccountsWidget(QWidget):
    """Виджет для управления Telegram аккаунтами"""
    
    def __init__(self, account_manager: AccountManager, database: Database):
        """
        Инициализация виджета аккаунтов
        
        Args:
            account_manager: Экземпляр AccountManager для работы с аккаунтами
            database: Экземпляр Database (для совместимости с PluginSystem)
        """
        super().__init__()
        self.account_manager = account_manager
        self.database = database
        self.init_ui()
        self.load_accounts()
        logger.info("AccountsWidget инициализирован")
    
    @staticmethod
    def get_info():
        """
        Возвращает информацию о плагине
        
        Returns:
            Словарь с информацией о плагине
        """
        return {
            "name": "Аккаунты",
            "icon": "👤",
            "description": "Управление Telegram аккаунтами"
        }
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        layout = QVBoxLayout()
        
        # ВЕРХНЯЯ ПАНЕЛЬ с кнопками (разбита на 2 строки)
        top_panel = QVBoxLayout()
        
        # Первая строка кнопок
        first_row = QHBoxLayout()
        
        # QComboBox "Выбрать диапазон"
        self.range_combo = QComboBox()
        self.range_combo.addItems(["Все", "Выбранные", "1-10", "11-20", "21-30"])
        first_row.addWidget(QLabel("Диапазон:"))
        first_row.addWidget(self.range_combo)
        
        # Кнопки управления (сокращённые тексты)
        self.manager_button = QPushButton("📊 Менеджер")
        self.manager_button.clicked.connect(self.show_placeholder)
        first_row.addWidget(self.manager_button)
        
        self.check_button = QPushButton("✓ Проверить")
        self.check_button.clicked.connect(self.show_placeholder)
        first_row.addWidget(self.check_button)
        
        self.check_no_spam_button = QPushButton("✓ Без @Spam")
        self.check_no_spam_button.clicked.connect(self.show_placeholder)
        first_row.addWidget(self.check_no_spam_button)
        
        self.set_photo_button = QPushButton("🖼️ Фото")
        self.set_photo_button.clicked.connect(self.show_placeholder)
        first_row.addWidget(self.set_photo_button)
        
        self.set_username_button = QPushButton("@ Username")
        self.set_username_button.clicked.connect(self.show_placeholder)
        first_row.addWidget(self.set_username_button)
        
        self.set_names_button = QPushButton("👤 Имена")
        self.set_names_button.clicked.connect(self.show_placeholder)
        first_row.addWidget(self.set_names_button)
        
        first_row.addStretch()
        top_panel.addLayout(first_row)
        
        # Вторая строка кнопок
        second_row = QHBoxLayout()
        
        self.delete_contacts_button = QPushButton("🗑️ Контакты")
        self.delete_contacts_button.clicked.connect(self.show_placeholder)
        second_row.addWidget(self.delete_contacts_button)
        
        self.end_sessions_button = QPushButton("🔒 Сессии")
        self.end_sessions_button.clicked.connect(self.show_placeholder)
        second_row.addWidget(self.end_sessions_button)
        
        self.set_2fa_button = QPushButton("🔐 2FA")
        self.set_2fa_button.clicked.connect(self.show_placeholder)
        second_row.addWidget(self.set_2fa_button)
        
        self.get_code_button = QPushButton("🔑 Код")
        self.get_code_button.clicked.connect(self.show_placeholder)
        second_row.addWidget(self.get_code_button)
        
        self.delete_button = QPushButton("🗑️ Удалить")
        self.delete_button.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.delete_button.clicked.connect(self.delete_selected)
        second_row.addWidget(self.delete_button)
        
        second_row.addStretch()
        top_panel.addLayout(second_row)
        
        layout.addLayout(top_panel)
        
        # ВТОРАЯ ПАНЕЛЬ с кнопками добавления
        second_panel = QHBoxLayout()
        
        self.add_button = QPushButton("Добавить аккаунт")
        self.add_button.clicked.connect(self.add_account_dialog)
        second_panel.addWidget(self.add_button)
        
        self.import_qr_button = QPushButton("Импорт через QR")
        self.import_qr_button.clicked.connect(self.show_placeholder)
        second_panel.addWidget(self.import_qr_button)
        
        self.import_json_button = QPushButton("Импорт JSON")
        self.import_json_button.clicked.connect(self.import_json)
        second_panel.addWidget(self.import_json_button)
        
        second_panel.addStretch()
        layout.addLayout(second_panel)
        
        # ТАБЛИЦА аккаунтов
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "№", "Аватар", "Имя", "Юзернейм", "Отлежка", "Гендер", "Прокси", "Телефон", "Статус"
        ])
        
        # Настройка ширины колонок (адаптивная)
        header = self.table.horizontalHeader()
        # Фиксированные колонки (по содержимому)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # №
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Аватар
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Гендер
        # Гибкие колонки (растягиваются)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Имя
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Юзернейм
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Отлежка
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # Прокси
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)  # Телефон
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)  # Статус
        
        # Включаем чекбоксы для выбора строк
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
        
        layout.addWidget(self.table)
        
        self.setLayout(layout)
    
    def generate_placeholder_delay(self):
        """Генерирует случайное значение отлежки"""
        delays = [
            f"{random.randint(1, 30)} дней",
            f"{random.randint(1, 60)} минут",
            f"{random.randint(1, 7)} дней",
            f"{random.randint(1, 24)} часов"
        ]
        return random.choice(delays)
    
    def generate_placeholder_gender(self):
        """Генерирует случайный гендер"""
        return random.choice(["♂️", "♀️"])
    
    def generate_placeholder_proxy(self):
        """Генерирует placeholder текст прокси"""
        proxies = [
            "Нет",
            "socks5://127.0.0.1:1080",
            "http://proxy.example.com:8080",
            "Нет прокси"
        ]
        return random.choice(proxies)
    
    def load_accounts(self):
        """Загружает список аккаунтов из AccountManager в таблицу с placeholder данными"""
        try:
            accounts = self.account_manager.get_all_accounts()
            
            # Очищаем таблицу
            self.table.setRowCount(0)
            
            # Заполняем таблицу
            for idx, account in enumerate(accounts, 1):
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                # №
                number_item = QTableWidgetItem(str(idx))
                number_item.setFlags(number_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 0, number_item)
                
                # Аватар (QLabel с placeholder "👤")
                avatar_label = QLabel("👤")
                avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setCellWidget(row, 1, avatar_label)
                
                # Имя (placeholder)
                name_item = QTableWidgetItem(f"User {account['id']}")
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 2, name_item)
                
                # Юзернейм (placeholder)
                username_item = QTableWidgetItem(f"user_{account['id']}")
                username_item.setFlags(username_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 3, username_item)
                
                # Отлежка (случайное значение)
                delay_item = QTableWidgetItem(self.generate_placeholder_delay())
                delay_item.setFlags(delay_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 4, delay_item)
                
                # Гендер (случайно)
                gender_item = QTableWidgetItem(self.generate_placeholder_gender())
                gender_item.setFlags(gender_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 5, gender_item)
                
                # Прокси (placeholder)
                proxy_item = QTableWidgetItem(self.generate_placeholder_proxy())
                proxy_item.setFlags(proxy_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 6, proxy_item)
                
                # Телефон
                phone_item = QTableWidgetItem(account['phone'])
                phone_item.setFlags(phone_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 7, phone_item)
                
                # Статус (зелёная плашка "Без ограничений")
                status_label = QLabel("Без ограничений")
                status_label.setStyleSheet("background-color: #4CAF50; color: white; padding: 2px 8px; border-radius: 3px;")
                status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setCellWidget(row, 8, status_label)
            
            logger.info(f"Загружено аккаунтов в таблицу: {len(accounts)}")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки аккаунтов: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось загрузить аккаунты: {str(e)}"
            )
    
    def add_account_dialog(self):
        """Диалог добавления нового аккаунта"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить аккаунт")
        dialog.setModal(True)
        
        layout = QFormLayout()
        
        # Поля ввода
        phone_input = QLineEdit()
        phone_input.setPlaceholderText("+79001234567")
        layout.addRow("Телефон:", phone_input)
        
        api_id_input = QLineEdit()
        api_id_input.setPlaceholderText("12345")
        layout.addRow("API ID:", api_id_input)
        
        api_hash_input = QLineEdit()
        api_hash_input.setPlaceholderText("abcdef1234567890")
        layout.addRow("API Hash:", api_hash_input)
        
        session_input = QLineEdit()
        session_input.setPlaceholderText("Опционально")
        layout.addRow("Session String:", session_input)
        
        # Кнопки диалога
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        dialog.setLayout(layout)
        
        # Показываем диалог
        if dialog.exec() == QDialog.DialogCode.Accepted:
            phone = phone_input.text().strip()
            api_id_str = api_id_input.text().strip()
            api_hash = api_hash_input.text().strip()
            session_string = session_input.text().strip() or None
            
            # Валидация
            if not phone:
                QMessageBox.warning(self, "Ошибка", "Введите номер телефона")
                return
            
            if not api_id_str:
                QMessageBox.warning(self, "Ошибка", "Введите API ID")
                return
            
            try:
                api_id = int(api_id_str)
            except ValueError:
                QMessageBox.warning(self, "Ошибка", "API ID должен быть числом")
                return
            
            if not api_hash:
                QMessageBox.warning(self, "Ошибка", "Введите API Hash")
                return
            
            # Добавляем аккаунт
            try:
                account_id = self.account_manager.add_account(
                    phone=phone,
                    api_id=api_id,
                    api_hash=api_hash,
                    session_string=session_string
                )
                
                QMessageBox.information(
                    self,
                    "Успех",
                    f"Аккаунт успешно добавлен! ID: {account_id}"
                )
                
                # Обновляем таблицу
                self.load_accounts()
                
            except ValueError as e:
                QMessageBox.warning(self, "Ошибка", str(e))
            except Exception as e:
                logger.error(f"Ошибка добавления аккаунта: {e}", exc_info=True)
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Не удалось добавить аккаунт: {str(e)}"
                )
    
    def delete_selected(self):
        """Удаление выбранных аккаунтов"""
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Выберите аккаунты для удаления"
            )
            return
        
        # Подтверждение удаления
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Вы уверены, что хотите удалить {len(selected_rows)} аккаунт(ов)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            for row in sorted(selected_rows, reverse=True):
                # Получаем телефон из таблицы (колонка 7)
                phone_item = self.table.item(row, 7)
                if phone_item:
                    phone = phone_item.text()
                    try:
                        success = self.account_manager.delete_account(phone)
                        if success:
                            deleted_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка удаления аккаунта {phone}: {e}", exc_info=True)
            
            if deleted_count > 0:
                QMessageBox.information(self, "Успех", f"Удалено аккаунтов: {deleted_count}")
                # Обновляем таблицу
                self.load_accounts()
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось удалить аккаунты")
    
    def import_json(self):
        """Импортирует аккаунты из JSON файла"""
        try:
            # Открываем диалог выбора файла
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Выберите JSON файл",
                "",
                "JSON Files (*.json);;All Files (*)"
            )
            
            if not file_path:
                return
            
            # Читаем и парсим JSON файл
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                error_msg = f"Ошибка парсинга JSON: {str(e)}"
                logger.error(error_msg)
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Файл содержит невалидный JSON:\n{error_msg}"
                )
                return
            except Exception as e:
                error_msg = f"Ошибка чтения файла: {str(e)}"
                logger.error(error_msg, exc_info=True)
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    error_msg
                )
                return
            
            # Проверяем, что данные - это список
            if not isinstance(data, list):
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "JSON файл должен содержать массив объектов"
                )
                return
            
            # Счётчики для результата
            imported_count = 0
            skipped_count = 0
            error_count = 0
            
            # Обрабатываем каждый аккаунт
            for idx, account_data in enumerate(data, 1):
                try:
                    # Валидация обязательных полей
                    if not isinstance(account_data, dict):
                        logger.warning(f"Запись {idx} не является объектом, пропуск")
                        skipped_count += 1
                        continue
                    
                    phone = account_data.get('phone')
                    api_id_str = account_data.get('api_id')
                    api_hash = account_data.get('api_hash')
                    session_string = account_data.get('session_string')
                    
                    # Проверка обязательных полей
                    if not phone:
                        logger.warning(f"Запись {idx}: отсутствует поле 'phone', пропуск")
                        skipped_count += 1
                        continue
                    
                    if not api_id_str:
                        logger.warning(f"Запись {idx}: отсутствует поле 'api_id', пропуск")
                        skipped_count += 1
                        continue
                    
                    if not api_hash:
                        logger.warning(f"Запись {idx}: отсутствует поле 'api_hash', пропуск")
                        skipped_count += 1
                        continue
                    
                    # Преобразуем api_id в int
                    try:
                        api_id = int(api_id_str)
                    except (ValueError, TypeError):
                        logger.warning(f"Запись {idx}: 'api_id' должен быть числом, пропуск")
                        skipped_count += 1
                        continue
                    
                    # Преобразуем session_string в None если пустая строка
                    if session_string and isinstance(session_string, str) and not session_string.strip():
                        session_string = None
                    
                    # Пытаемся добавить аккаунт
                    try:
                        account_id = self.account_manager.add_account(
                            phone=str(phone).strip(),
                            api_id=api_id,
                            api_hash=str(api_hash).strip(),
                            session_string=session_string.strip() if session_string else None
                        )
                        imported_count += 1
                        logger.info(f"Импортирован аккаунт: {phone} (ID: {account_id})")
                        
                    except ValueError as e:
                        # Дубликат или другая ошибка валидации
                        logger.warning(f"Пропущен аккаунт {phone}: {str(e)}")
                        skipped_count += 1
                        
                    except Exception as e:
                        # Неожиданная ошибка
                        logger.error(f"Ошибка импорта аккаунта {phone}: {e}", exc_info=True)
                        error_count += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка обработки записи {idx}: {e}", exc_info=True)
                    error_count += 1
            
            # Показываем результат
            result_message = f"Импорт завершён!\n\n"
            result_message += f"Импортировано: {imported_count}\n"
            result_message += f"Пропущено: {skipped_count}\n"
            if error_count > 0:
                result_message += f"Ошибок: {error_count}"
            
            if imported_count > 0:
                QMessageBox.information(
                    self,
                    "Импорт завершён",
                    result_message
                )
                # Обновляем таблицу после успешного импорта
                self.load_accounts()
            else:
                QMessageBox.warning(
                    self,
                    "Импорт завершён",
                    result_message
                )
            
            logger.info(f"Импорт JSON завершён: импортировано={imported_count}, пропущено={skipped_count}, ошибок={error_count}")
            
        except Exception as e:
            error_msg = f"Критическая ошибка импорта: {str(e)}"
            logger.error(error_msg, exc_info=True)
            QMessageBox.critical(
                self,
                "Ошибка",
                error_msg
            )
    
    def show_placeholder(self):
        """Показывает сообщение о том, что функция в разработке"""
        QMessageBox.information(
            self,
            "В разработке",
            "Эта функция находится в разработке и будет добавлена в следующих версиях."
        )
