// core/webapp/static/main.js
document.addEventListener('DOMContentLoaded', () => {
    const tg = window.Telegram.WebApp;
    tg.expand(); // Расширяем приложение на весь экран

    const columns = {
        new: document.getElementById('new'),
        in_progress: document.getElementById('in_progress'),
        ready: document.getElementById('ready'),
    };

    // Функция для отрисовки карточки заказа
    function renderOrder(order) {
        const card = document.createElement('div');
        card.className = 'order-card';
        card.id = `order-${order.id}`;
        card.innerHTML = `
            <h3>Заказ №${order.id}</h3>
            <p><b>Напиток:</b> ${order.drink}</p>
            <p><b>Тара:</b> ${order.cup}</p>
            <p><b>Подойдет через:</b> ${order.time_to_come}</p>
            <div class="actions"></div>
        `;

        const actions = card.querySelector('.actions');
        if (order.status === 'new') {
            const btn = document.createElement('button');
            btn.innerText = 'Принять в работу';
            btn.onclick = () => updateOrderStatus(order.id, 'in_progress');
            actions.appendChild(btn);
        } else if (order.status === 'in_progress') {
            const btn = document.createElement('button');
            btn.innerText = 'Готов';
            btn.onclick = () => updateOrderStatus(order.id, 'ready');
            actions.appendChild(btn);
        } else if (order.status === 'ready') {
            const btn = document.createElement('button');
            btn.innerText = 'Завершить';
            btn.onclick = () => updateOrderStatus(order.id, 'completed');
            actions.appendChild(btn);
        }

        columns[order.status].appendChild(card);
    }

    // Функция для перемещения карточки заказа
    function moveOrder(orderId, newStatus) {
        const card = document.getElementById(`order-${orderId}`);
        if (!card) return;

        if (newStatus === 'completed') {
            card.remove(); // Удаляем завершенный заказ с доски
        } else {
            // Перерисовываем карточку в новой колонке
            const orderData = {
                id: orderId,
                drink: card.querySelector('p:nth-child(2)').innerText.split(': ')[1],
                cup: card.querySelector('p:nth-child(3)').innerText.split(': ')[1],
                time_to_come: card.querySelector('p:nth-child(4)').innerText.split(': ')[1],
                status: newStatus,
            };
            card.remove();
            renderOrder(orderData);
        }
    }

    // Загружаем активные заказы при открытии
    async function fetchOrders() {
        try {
            const response = await fetch('/api/orders');
            const orders = await response.json();
            // Очищаем колонки перед отрисовкой
            Object.values(columns).forEach(col => col.innerHTML = `<h2>${col.querySelector('h2').innerText}</h2>`);
            orders.forEach(renderOrder);
        } catch (error) {
            console.error("Failed to fetch orders:", error);
            tg.showAlert("Не удалось загрузить заказы.");
        }
    }

    // Обновляем статус заказа
    async function updateOrderStatus(orderId, newStatus) {
        try {
            await fetch(`/api/orders/${orderId}/status?status=${newStatus}`, { method: 'PUT' });
            // После успешного запроса, WebSocket сам пришлет обновление,
            // поэтому вручную перемещать не нужно. Но для надежности можно и переместить.
            moveOrder(orderId, newStatus);
        } catch (error) {
            console.error("Failed to update status:", error);
            tg.showAlert("Не удалось обновить статус заказа.");
        }
    }

    // Подключаемся к WebSocket
    function connectWebSocket() {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${proto}//${window.location.host}/ws/orders`);

        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);

            if (data.type === 'new_order') {
                renderOrder(data.payload);
                tg.HapticFeedback.notificationOccurred('success'); // Вибрация при новом заказе
            } else if (data.type === 'status_update') {
                moveOrder(data.payload.order_id, data.payload.new_status);
            }
        };

        ws.onclose = function() {
            console.log('WebSocket closed. Reconnecting in 3 seconds...');
            setTimeout(connectWebSocket, 3000); // Попытка переподключения
        };

        ws.onerror = function(error) {
            console.error('WebSocket Error:', error);
            ws.close();
        };
    }

    fetchOrders();
    connectWebSocket();
});