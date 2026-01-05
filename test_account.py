"""
Тестовый файл для проверки работы AccountManager
"""

import logging
from src.core.database import Database
from src.core.account_manager import AccountManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    """Тестирование AccountManager"""
    # Создание тестовой базы данных
    db = Database("test_accounts.db")
    
    try:
        # Подключение и создание таблиц
        db.connect()
        db.create_tables()
        print("✅ База данных создана и таблицы инициализированы\n")
        
        # Создание менеджера аккаунтов
        account_manager = AccountManager(db)
        print("✅ AccountManager инициализирован\n")
        
        # Тест 1: Добавление аккаунта
        print("=" * 50)
        print("ТЕСТ 1: Добавление аккаунта")
        print("=" * 50)
        try:
            account_id = account_manager.add_account(
                phone="+79001234567",
                api_id=12345,  # Должен быть int, а не str
                api_hash="test_hash_123",
                session_string="test_session"
            )
            print(f"✅ Аккаунт успешно добавлен! ID: {account_id}\n")
        except Exception as e:
            print(f"❌ Ошибка добавления аккаунта: {e}\n")
        
        # Тест 2: Получение всех аккаунтов
        print("=" * 50)
        print("ТЕСТ 2: Получение всех аккаунтов")
        print("=" * 50)
        try:
            accounts = account_manager.get_all_accounts()
            print(f"✅ Найдено аккаунтов: {len(accounts)}")
            for account in accounts:
                print(f"  - ID: {account['id']}, Телефон: {account['phone']}, "
                      f"API ID: {account['api_id']}, Создан: {account['created_at']}")
            print()
        except Exception as e:
            print(f"❌ Ошибка получения аккаунтов: {e}\n")
        
        # Тест 3: Поиск аккаунта по номеру
        print("=" * 50)
        print("ТЕСТ 3: Поиск аккаунта по номеру телефона")
        print("=" * 50)
        try:
            account = account_manager.get_account_by_phone("+79001234567")
            if account:
                print(f"✅ Аккаунт найден!")
                print(f"  - ID: {account['id']}")
                print(f"  - Телефон: {account['phone']}")
                print(f"  - API ID: {account['api_id']}")
                print(f"  - API Hash: {account['api_hash']}")
                print(f"  - Session String: {account['session_string']}")
                print(f"  - Создан: {account['created_at']}\n")
            else:
                print("❌ Аккаунт не найден\n")
        except Exception as e:
            print(f"❌ Ошибка поиска аккаунта: {e}\n")
        
        # Тест 4: Поиск несуществующего аккаунта
        print("=" * 50)
        print("ТЕСТ 4: Поиск несуществующего аккаунта")
        print("=" * 50)
        try:
            account = account_manager.get_account_by_phone("+79999999999")
            if account:
                print(f"❌ Неожиданно найден аккаунт: {account['phone']}\n")
            else:
                print("✅ Аккаунт не найден (ожидаемое поведение)\n")
        except Exception as e:
            print(f"❌ Ошибка поиска: {e}\n")
        
        # Тест 5: Попытка добавить дубликат
        print("=" * 50)
        print("ТЕСТ 5: Попытка добавить дубликат аккаунта")
        print("=" * 50)
        try:
            account_manager.add_account(
                phone="+79001234567",
                api_id=12345,
                api_hash="test_hash_123",
                session_string="test_session"
            )
            print("❌ Дубликат был добавлен (неожиданное поведение)\n")
        except ValueError as e:
            print(f"✅ Дубликат корректно отклонён: {e}\n")
        except Exception as e:
            print(f"❌ Неожиданная ошибка: {e}\n")
        
        print("=" * 50)
        print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
    finally:
        # Закрытие соединения с БД
        db.close()
        print("\n✅ Соединение с базой данных закрыто")


if __name__ == "__main__":
    main()

