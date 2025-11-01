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

    let allActiveOrders = [];
    let activeStatus = 'new';

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const newStatus = tab.dataset.status;
            if (newStatus === activeStatus) return;
            activeStatus = newStatus;
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            if (activeStatus === 'completed') {
                fetchCompletedOrders();
            } else {
                renderVisibleOrders();
            }
        });
    });

    // --- Функции рендеринга ---

    function renderVisibleOrders() {
        if (!ordersContainer) return;
        ordersContainer.innerHTML = '';
        const visibleOrders = allActiveOrders.filter(order => order.status === activeStatus);

        if (visibleOrders.length === 0) {
            ordersContainer.innerHTML = '<p class="empty-state">Здесь пока нет заказов</p>';
            return;
        }

        visibleOrders
            .sort((a, b) => a.order_id - b.order_id)
            .forEach(renderOrderCard);
    }

    function renderCompletedOrders(completedOrders) {
        if (!ordersContainer) return;
        ordersContainer.innerHTML = '';

        if (completedOrders.length === 0) {
            ordersContainer.innerHTML = '<p class="empty-state">За сегодня нет завершенных заказов</p>';
            return;
        }

        completedOrders
            .sort((a, b) => b.order_id - a.order_id)
            .forEach(renderOrderCard);
    }

    function renderOrderCard(order) {
        if (!ordersContainer) return;
        const card = document.createElement('div');
        card.className = 'order-card';
        card.dataset.orderId = order.order_id;
        const icons = { type: '☕️', syrup: '🍯', cup: '🥤', croissant: '🥐', price: '💰', time: '🕒' };

        const createdTime = new Date(order.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

        const timeHTML = activeStatus !== 'completed'
            ? `<p>${icons.time} <b>Подойдет через:</b> ${order.time || '?'}</p>`
            : '';

        let paymentStatusHTML = '';
        if (order.payment_status === 'paid') {
            paymentStatusHTML = `<p class="payment-status paid">✅ ОПЛАЧЕНО ОНЛАЙН</p>`;
        } else if (order.payment_status === 'bonus') {
            paymentStatusHTML = `<p class="payment-status bonus">🎁 ОПЛАЧЕНО БОНУСОМ</p>`;
        } else { // unpaid
            paymentStatusHTML = `<p class="payment-status unpaid">❗️ ОПЛАТА НА МЕСТЕ</p>`;
        }

        card.innerHTML = `
            <h3>Заказ №${order.order_id}</h3>
            ${paymentStatusHTML}
            <div class="order-details">
                <p>${icons.type} <b>Напиток:</b> ${order.type || '?'}</p>
                <p>${icons.syrup} <b>Сироп:</b> ${order.syrup || 'Нет'}</p>
                <p>${icons.cup} <b>Объем:</b> ${order.cup || '?'}</p>
                <p>${icons.croissant} <b>Добавка:</b> ${order.croissant || 'Нет'}</p>
                <p>${icons.time} <b>Создан:</b> ${createdTime}</p>
                ${timeHTML}
            </div>

            <div class="order-footer">
                <p>${icons.price} <b>Сумма:</b> ${order.total_price || '?'} Т</p>
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
            button.className = 'cancel';
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
    }

    // --- Сетевые функции ---

    async function fetchActiveOrders() {
        try {
            const response = await fetch('/api/orders/');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            allActiveOrders = await response.json();
            if (activeStatus !== 'completed') {
                renderVisibleOrders();
            }
        } catch (error) {
            console.error("Failed to fetch active orders:", error);
            if (ordersContainer && activeStatus !== 'completed') {
                ordersContainer.innerHTML = `<p class="empty-state">Ошибка: ${error.message}.</p>`;
            }
        }
    }

    async function fetchCompletedOrders() {
        try {
            const response = await fetch('/api/orders/completed');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const completedOrders = await response.json();
            renderCompletedOrders(completedOrders);
        } catch (error) {
            console.error("Failed to fetch completed orders:", error);
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
            fetchActiveOrders();
            if (activeStatus === 'completed') {
                fetchCompletedOrders();
            }

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
    fetchActiveOrders();
    connectWebSocket();
});