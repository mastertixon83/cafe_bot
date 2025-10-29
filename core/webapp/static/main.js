document.addEventListener('DOMContentLoaded', () => {
    // --- Инициализация ---
    const tg = window.Telegram.WebApp;
    if (tg) {
        tg.expand();
        tg.setHeaderColor('#1a1a1a');
        tg.setBackgroundColor('#1a1a1a');
    }

    // --- Поиск элементов ---
    const ordersContainer = document.getElementById('orders-container');
    const statusIndicator = document.getElementById('status-indicator');
    const tabs = document.querySelectorAll('.tab-button');

    // --- Состояние приложения ---
    let allOrders = [];
    let activeStatus = 'new';

    // --- Обработчики событий ---
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            activeStatus = tab.dataset.status;
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            renderVisibleOrders();
        });
    });

    // --- Функции рендеринга ---
    function renderVisibleOrders() {
        if (!ordersContainer) return;
        ordersContainer.innerHTML = '';
        const visibleOrders = allOrders.filter(order => order.status === activeStatus);

        if (visibleOrders.length === 0) {
            ordersContainer.innerHTML = '<p class="empty-state">Здесь пока нет заказов</p>';
            return;
        }

        visibleOrders
            .sort((a, b) => a.order_id - b.order_id)
            .forEach(renderOrderCard);
    }

    // --- НАЧАЛО ИСПРАВЛЕНИЯ (ТОЛЬКО ЭТА ФУНКЦИЯ) ---
    function renderOrderCard(order) {
        if (!ordersContainer) return;
        const card = document.createElement('div');
        card.className = 'order-card';
        card.dataset.orderId = order.order_id;
        const icons = { type: '☕️', syrup: '🍯', cup: '🥤', croissant: '🥐', time: '🕒' };

        card.innerHTML = `
            <h3>Заказ №${order.order_id}</h3>
            <div class="order-details">
                <p>${icons.type} <b>Напиток:</b> ${order.type || '?'}</p>
                <p>${icons.syrup} <b>Сироп:</b> ${order.syrup || 'Нет'}</p>
                <p>${icons.cup} <b>Объем:</b> ${order.cup || '?'}</p>
                <p>${icons.croissant} <b>Добавка:</b> ${order.croissant || 'Нет'}</p>
                <p>${icons.time} <b>Подойдет через:</b> ${order.time || '?'}</p>
            </div>
            <div class="actions"></div>
        `;

        const actions = card.querySelector('.actions');

        // Очищаем блок actions перед заполнением
        actions.innerHTML = '';

        if (order.status === 'new') {
            const button = document.createElement('button');
            button.innerText = 'Принять в работу';
            button.className = 'new';
            button.onclick = () => updateOrderStatus(order.order_id, 'in_progress');
            actions.appendChild(button);
        } else if (order.status === 'in_progress') {
            const button = document.createElement('button');
            button.innerText = 'Готов к выдаче';
            button.className = 'in_progress';
            button.onclick = () => updateOrderStatus(order.order_id, 'ready');
            actions.appendChild(button);
        } else if (order.status === 'ready') {
            // Создаем и добавляем текст
            const infoText = document.createElement('p');
            infoText.className = 'info-text';
            infoText.textContent = 'Ожидает клиента';
            actions.appendChild(infoText);

            // Создаем и добавляем кнопку
            const button = document.createElement('button');
            button.innerText = 'Завершить (если забрал)';
            button.className = 'ready';
            button.style.marginTop = '10px';
            button.onclick = () => updateOrderStatus(order.order_id, 'completed');
            actions.appendChild(button);
        } else if (order.status === 'arrived') {
            const button = document.createElement('button');
            button.innerText = 'Завершить';
            button.className = 'ready';
            button.onclick = () => updateOrderStatus(order.order_id, 'completed');
            actions.appendChild(button);
        }

        ordersContainer.appendChild(card);
    }
    // --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    // --- Сетевые функции ---
    async function fetchAndUpdateAllOrders() {
        try {
            const response = await fetch('/api/orders/');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            allOrders = await response.json();
            renderVisibleOrders();
        } catch (error) {
            console.error("Failed to fetch orders:", error);
            if (ordersContainer) {
                ordersContainer.innerHTML = `<p class="empty-state">Ошибка: ${error.message}. Попробуйте перезапустить.</p>`;
            }
        }
    }

    async function updateOrderStatus(orderId, newStatus) {
        try {
            const response = await fetch(`/api/orders/${orderId}/status?status=${newStatus}`, { method: 'PUT' });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        } catch (error) {
            console.error("Failed to update status:", error);
            if (tg) tg.showAlert("Не удалось обновить статус заказа.");
        }
    }

    function connectWebSocket() {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${proto}//${window.location.host}/ws/orders`);

        ws.onopen = () => { if (statusIndicator) statusIndicator.className = 'connected'; };
        ws.onmessage = (event) => {
            console.log('Update from server...');
            fetchAndUpdateAllOrders();
            const data = JSON.parse(event.data);
            if (data.type === 'new_order' && tg) {
                tg.HapticFeedback.notificationOccurred('success');
            }
        };
        ws.onclose = () => {
            if (statusIndicator) statusIndicator.className = 'disconnected';
            setTimeout(connectWebSocket, 3000);
        };
        ws.onerror = (error) => {
            console.error('WebSocket Error:', error);
            if (statusIndicator) statusIndicator.className = 'disconnected';
            ws.close();
        };
    }

    // --- Запуск приложения ---
    fetchAndUpdateAllOrders();
    connectWebSocket();
});