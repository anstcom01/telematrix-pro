"""
Тестовый файл для проверки работы базы данных TeleMatrix Pro
"""

import logging
from src.core.database import Database

# Настройка логирования для вывода информации
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    """Тестирование базы данных"""
    # Создание экземпляра Database с тестовой базой
    db = Database("test.db")
    
    try:
        # Подключение к базе данных
        db.connect()
        
        # Создание таблиц
        db.create_tables()
        print("✅ Таблицы созданы успешно!")
        
        # Получение списка таблиц
        tables_query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        tables = db.fetch_all(tables_query)
        
        # Вывод информации о таблицах
        print(f"\n📊 Найдено таблиц: {len(tables)}")
        print("\nСписок таблиц:")
        for table in tables:
            print(f"  - {table['name']}")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
    finally:
        # Закрытие соединения
        db.close()
        print("\n✅ Соединение с базой данных закрыто")


if __name__ == "__main__":
    main()

