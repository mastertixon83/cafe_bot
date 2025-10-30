# core/utils/helpers.py

# --- 1. ПРАЙС-ЛИСТ ---
# Теперь прайс-лист живет здесь, в одном месте
PRICES = {
    "coffee": {
        "Эспрессо": {"250": 800, "330": 800, "430": 800},
        "Американо": {"250": 900, "330": 1100, "430": 1300},
        "Капучино": {"250": 1200, "330": 1400, "430": 1600},
        "Лате": {"250": 1200, "330": 1400, "430": 1600},
    },
    "syrup": 300,
    "croissant": 700
}


# --- 2. ФУНКЦИЯ ПОДСЧЕТА СТОИМОСТИ ---
# Теперь эта функция тоже живет здесь
def calculate_order_total(order_data: dict) -> int:
    """Рассчитывает общую стоимость заказа на основе данных FSM или словаря из БД."""
    total_price = 0
    coffee_type = order_data.get('type')
    cup_size = str(order_data.get('cup'))  # Преобразуем в строку на всякий случай
    syrup = order_data.get('syrup')
    croissant = order_data.get('croissant')

    if coffee_type and cup_size:
        total_price += PRICES.get("coffee", {}).get(coffee_type, {}).get(cup_size, 0)
    if syrup and syrup != "Без сиропа":
        total_price += PRICES.get("syrup", 0)
    if croissant and croissant != "Без добавок":
        total_price += PRICES.get("croissant", 0)
    return total_price
