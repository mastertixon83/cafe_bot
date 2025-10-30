document.addEventListener('DOMContentLoaded', () => {
    const tg = window.Telegram.WebApp;
    if (tg) {
        tg.expand();
        tg.setHeaderColor('#1a1a1a');
        tg.setBackgroundColor('#1a1a1a');
    }

    const ordersContainer = document.getElementById('orders-container');
    const statusIndicator = document.getElementById('status-indicator');
    const tabs = document.querySelectorAll('.tab-button');

    let activeStatus = 'new';

    // --- ОБРАБОТЧИКИ ---
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            activeStatus = tab.dataset.status;
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            // При клике на любую вкладку, просто запрашиваем данные заново
            fetchAndUpdateOrders();
        });
    });

    // --- ГЛАВНАЯ ФУНКЦИЯ ЗАГРУЗКИ И ОТРИСОВКИ ---
    async function fetchAndUpdateOrders() {
        // Определяем, какой URL использовать в зависимости от активной вкладки
        let url = '/api/orders/';
        if (activeStatus === 'completed') {
            url = '/api/orders/completed';
        }

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const orders = await response.json();

            // --- НАЧАЛО БЛОКА РЕНДЕРИНГА ---
            if (!ordersContainer) return;
            ordersContainer.innerHTML = ''; // Очищаем контейнер

            if (orders.length === 0) {
                const message = activeStatus === 'completed' ? 'За сегодня нет завершенных заказов' : 'Здесь пока нет заказов';
                ordersContainer.innerHTML = `<p class="empty-state">${message}</p>`;
                return;
            }

            // Фильтруем заказы (на случай, если API вернуло лишнее)
            const visibleOrders = orders.filter(order => order.status === activeStatus);

            // Сортируем
            visibleOrders.sort((a, b) => activeStatus === 'completed' ? b.order_id - a.order_id : a.order_id - b.order_id);

            // Рендерим каждую карточку
            visibleOrders.forEach(order => {
                const card = document.createElement('div');
                card.className = 'order-card';
                card.dataset.orderId = order.order_id;
                const icons = { type: '☕️', syrup: '🍯', cup: '🥤', croissant: '🥐', price: '💰', time: '🕒' };

                const timeHTML = activeStatus !== 'completed'
                    ? `<p>${icons.time} <b>Подойдет через:</b> ${order.time || '?'}</p>`
                    : '';

                card.innerHTML = `
                    <h3>Заказ №${order.order_id}</h3>
                    <div class="order-details">
                        <p>${icons.type} <b>Напиток:</b> ${order.type || '?'}</p>
                        <p>${icons.syrup} <b>Сироп:</b> ${order.syrup || 'Нет'}</p>
                        <p>${icons.cup} <b>Объем:</b> ${order.cup || '?'}</p>
                        <p>${icons.croissant} <b>Добавка:</b> ${order.croissant || 'Нет'}</p>
                        <p>${icons.price} <b>Сумма:</b> ${order.total_price || '?'} Т</p>
                        ${timeHTML}
                    </div>
                    <div class="actions"></div>
                `;

                const actions = card.querySelector('.actions');
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
                    const infoText = document.createElement('p');
                    infoText.className = 'info-text';
                    infoText.textContent = 'Ожидает клиента';
                    actions.appendChild(infoText);

                    const button = document.createElement('button');
                    button.innerText = 'Завершить (клиент не пришел)';
                    button.className = 'cancel'; // Серый цвет
                    button.style.marginTop = '10px';
                    button.onclick = () => updateOrderStatus(order.order_id, 'completed');
                    actions.appendChild(button);
                } else if (order.status === 'arrived') {
                    const button = document.createElement('button');
                    button.innerText = 'Завершить';
                    button.className = 'ready';
                    button.onclick = () => updateOrderStatus(order.order_id, 'completed');
                    actions.appendChild(button);
                } else if (order.status === 'completed') {
                    const infoText = document.createElement('p');
                    infoText.className = 'info-text';
                    const completedTime = new Date(order.updated_at || order.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
                    infoText.textContent = `Завершен в ${completedTime}`;
                    actions.appendChild(infoText);
                }

                ordersContainer.appendChild(card);
            });
            // --- КОНЕЦ БЛОКА РЕНДЕРИНГА ---

        } catch (error) {
            console.error(`Failed to fetch orders from ${url}:`, error);
            if (ordersContainer) {
                ordersContainer.innerHTML = `<p class="empty-state">Ошибка: ${error.message}.</p>`;
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
            // При любом обновлении просто перезапрашиваем данные для текущей вкладки
            fetchAndUpdateOrders();

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
    fetchAndUpdateOrders();
    connectWebSocket();
});