
const API_URL = "http://127.0.0.1:8000";

let mediaRecorder;
let audioChunks = [];
let previewData = null;
let confirmationKey = null;
let isRecording = false;
let originalRequestedItems = [];
let selectedAlternatives = {};
let alternativeCustomerName = null;
let unavailableItems = [];

const recordButton = document.getElementById("recordButton");
const recordStatus = document.getElementById("recordStatus");
const transcript = document.getElementById("transcript");
const orderDetails = document.getElementById("orderDetails");
const confirmButton = document.getElementById("confirmButton");

recordButton.addEventListener("click", async () => {

    if (isRecording) {
        mediaRecorder.stop();
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: true
        });

        audioChunks = [];

        const mimeType = MediaRecorder.isTypeSupported("audio/webm")
            ? "audio/webm"
            : "";

        mediaRecorder = new MediaRecorder(
            stream,
            mimeType ? { mimeType } : undefined
        );

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = async () => {

            stream.getTracks().forEach(track => track.stop());

            const audioBlob = new Blob(audioChunks, {
                type: mediaRecorder.mimeType
            });

            await uploadAudio(audioBlob);
        };

        mediaRecorder.start();
        isRecording = true;

        recordButton.textContent = "⏹ Stop Recording";
        recordButton.classList.add("recording");
        recordStatus.textContent = "Listening... Speak your order.";

    } catch (error) {
        recordStatus.textContent =
            "Microphone access failed: " + error.message;
    }
});



// Convert browser-recorded audio into WAV format
async function convertToWav(audioBlob) {

    const audioContext = new AudioContext();

    try {
        const arrayBuffer = await audioBlob.arrayBuffer();

        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

        const sampleRate = audioBuffer.sampleRate;
        const numberOfFrames = audioBuffer.length;
        const numberOfChannels = 1;

        // Convert stereo audio to mono
        const monoData = new Float32Array(numberOfFrames);

        for (let channel = 0; channel < audioBuffer.numberOfChannels; channel++) {
            const channelData = audioBuffer.getChannelData(channel);

            for (let i = 0; i < numberOfFrames; i++) {
                monoData[i] += channelData[i] / audioBuffer.numberOfChannels;
            }
        }

        // Create WAV file
        const buffer = new ArrayBuffer(44 + numberOfFrames * 2);
        const view = new DataView(buffer);

        function writeString(offset, string) {
            for (let i = 0; i < string.length; i++) {
                view.setUint8(offset + i, string.charCodeAt(i));
            }
        }

        writeString(0, "RIFF");
        view.setUint32(4, 36 + numberOfFrames * 2, true);
        writeString(8, "WAVE");
        writeString(12, "fmt ");
        view.setUint32(16, 16, true);
        view.setUint16(20, 1, true);
        view.setUint16(22, numberOfChannels, true);
        view.setUint32(24, sampleRate, true);
        view.setUint32(28, sampleRate * 2, true);
        view.setUint16(32, 2, true);
        view.setUint16(34, 16, true);
        writeString(36, "data");
        view.setUint32(40, numberOfFrames * 2, true);

        let offset = 44;

        for (let i = 0; i < numberOfFrames; i++) {
            const sample = Math.max(-1, Math.min(1, monoData[i]));

            view.setInt16(
                offset,
                sample < 0 ? sample * 32768 : sample * 32767,
                true
            );

            offset += 2;
        }

        return new Blob([buffer], { type: "audio/wav" });

    } finally {
        await audioContext.close();
    }
}

function renderAlternativeOptions(result) {

    previewData = null;
    confirmationKey = null;
    confirmButton.disabled = true;

    originalRequestedItems = result.requested_items;
    unavailableItems = result.unavailable_items;
    selectedAlternatives = {};
    alternativeCustomerName = result.customer_name;

    let html = `
        <h3>⚠ Product Availability</h3>
        <p>${result.message}</p>
    `;

    unavailableItems.forEach((item, index) => {

        html += `
            <div class="alternative-card">
                <h4>${item.requested_product}</h4>
                <p>Requested: ${item.requested_quantity} ${item.unit}</p>
                <p>Available: ${item.available_stock} ${item.unit}</p>
                <h4>Suggested Alternatives</h4>
        `;

        if (!item.suggestions || item.suggestions.length === 0) {
            html += `
                <p class="warning-message">
                    No alternatives available.
                </p>
            `;
        }

        item.suggestions.forEach(suggestion => {

            html += `
                <label class="alternative-option">
                    <input
                        type="radio"
                        name="alternative-${index}"
                        value="${suggestion.product}"
                        onchange="selectAlternative(${item.item_index}, '${suggestion.product.replace(/'/g, "\\'")}')"
                    >
                    <strong>${suggestion.product}</strong>
                    <span>
                        Stock: ${suggestion.available_stock} ${suggestion.unit}
                    </span>
                    <span>Price: ₹${suggestion.price}</span>
                </label>
            `;
        });

        html += `</div>`;
    });

    // Show preview button only if every unavailable item
    // has at least one suitable alternative
    const canPreview = unavailableItems.every(
        item => item.suggestions && item.suggestions.length > 0
    );

    if (canPreview) {

        html += `
            <button
                type="button"
                class="confirm-button"
                onclick="previewSelectedAlternatives()"
            >
                Preview Updated Bill
            </button>
        `;

    } else {

        html += `
            <p class="warning-message">
                No suitable alternative has sufficient stock.
                Please reduce the quantity or try another product.
            </p>
        `;
    }

    orderDetails.innerHTML = html;

    recordStatus.textContent = canPreview
        ? "Please select an alternative product."
        : "No suitable alternative available.";
}
// Upload converted WAV audio to FastAPI
async function uploadAudio(audioBlob) {

    isRecording = false;

    recordButton.textContent = "🎙 Start Recording";
    recordButton.classList.remove("recording");

    recordStatus.textContent = "Converting audio to WAV...";

    try {

        const wavBlob = await convertToWav(audioBlob);

        const formData = new FormData();

        formData.append("audio", wavBlob, "kirana_order.wav");

        recordStatus.textContent = "Processing your voice...";

        const response = await fetch(
            `${API_URL}/voice/preview-order`,
            {
                method: "POST",
                body: formData
            }
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "Voice processing failed");
        }

        transcript.textContent =
            JSON.stringify(result.transcripts || result, null, 2);

        if (result.status === "alternative_required") {

            renderAlternativeOptions(result);
            return;
        }

        if (result.status === "clarification_required") {

            previewData = null;
            confirmationKey = null;
            confirmButton.disabled = true;

            orderDetails.textContent = result.message;
            recordStatus.textContent = result.message;

            return;
        }

        if (result.status === "confirmation_required") {

            previewData = result;
            confirmationKey = crypto.randomUUID();

            orderDetails.innerHTML = `
                <h3>Order Preview</h3>
                <p>Customer: ${result.customer_name}</p>
                ${result.items.map(item => `
                    <p>
                        ${item.product} —
                        ${item.quantity} ${item.unit} —
                        ₹${item.subtotal}
                    </p>
                `).join("")}
                <h3>Total: ₹${result.total_amount}</h3>
                <p>${result.message}</p>
            `;

            confirmButton.disabled = false;
            confirmButton.textContent = "✓ Confirm Order";

            recordStatus.textContent =
                "Voice processed successfully!";

        }

    } catch (error) {

        console.error("Audio processing error:", error);

        recordStatus.textContent = "Error: " + error.message;

        previewData = null;
        confirmationKey = null;
        confirmButton.disabled = true;
    }
}


confirmButton.addEventListener("click", async () => {

    if (!previewData || !confirmationKey) {
        alert("Please record and preview an order first.");
        return;
    }

    confirmButton.disabled = true;
    confirmButton.textContent = "Processing Order...";

    recordStatus.textContent = "Confirming your order...";

    try {

        // Prepare the confirmed order
        const orderPayload = {
            customer_name: previewData.customer_name,
            items: previewData.items.map(item => ({
                product: item.product,
                quantity: item.quantity,
                unit: item.unit
            }))
        };

        // Save the order through FastAPI
        const response = await fetch(
            `${API_URL}/voice/confirm-order`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Idempotency-Key": confirmationKey
                },
                body: JSON.stringify(orderPayload)
            }
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "Order confirmation failed");
        }

        recordStatus.textContent =
            `Order #${result.order_id} confirmed successfully!`;

        orderDetails.textContent =
            `Order ID: ${result.order_id}\n` +
            `Customer: ${result.customer_name}\n` +
            `Total: ₹${result.total_amount}\n` +
            `Status: Confirmed`;

        confirmButton.textContent = "✓ Order Confirmed";

        // Generate Telugu voice confirmation
        recordStatus.textContent =
            "Generating Telugu voice confirmation...";

        const audioResponse = await fetch(
            `${API_URL}/voice/speak-order/${result.order_id}`,
            {
                method: "POST",
                headers: {
                    "Accept": "audio/wav"
                }
            }
        );

        if (!audioResponse.ok) {
            throw new Error("Order saved, but voice generation failed.");
        }

        const audioBlob = await audioResponse.blob();

        const audioUrl = URL.createObjectURL(audioBlob);

        const audioPlayer =
            document.getElementById("confirmationAudio");

        audioPlayer.src = audioUrl;
        audioPlayer.hidden = false;

        await audioPlayer.play();

        recordStatus.textContent =
            "Order confirmed! DukaanSathi is speaking.";

        // Prevent another confirmation using this preview
        previewData = null;
        confirmationKey = null;

    } catch (error) {

        console.error("Order confirmation error:", error);

        recordStatus.textContent = error.message;

        // Don't allow accidental resubmission of an already saved order
        if (error.message.includes("voice generation failed")) {
            confirmButton.textContent = "✓ Order Saved";
        } else {
            confirmButton.disabled = false;
            confirmButton.textContent = "✓ Retry Confirmation";
        }
    }
});


// ==========================================
// SMART INVENTORY DASHBOARD
// ==========================================

async function loadDashboardData() {
    try {
        const [productsResponse, ordersResponse, alertsResponse] =
            await Promise.all([
                fetch(`${API_URL}/products`),
                fetch(`${API_URL}/orders`),
                fetch(`${API_URL}/inventory/low-stock`)
            ]);

        if (!productsResponse.ok ||
            !ordersResponse.ok ||
            !alertsResponse.ok) {
            throw new Error("Unable to load dashboard data");
        }

        const products = await productsResponse.json();
        const orders = await ordersResponse.json();
        const lowStockData = await alertsResponse.json();

        // Update dashboard statistics
        document.getElementById("totalProducts").textContent =
            products.length;

        document.getElementById("totalOrders").textContent =
            orders.length;

        const totalSales = orders.reduce(
            (sum, order) => sum + Number(order.total_amount || 0),
            0
        );

        document.getElementById("totalSales").textContent =
            `₹ ${totalSales.toFixed(2)}`;

        document.getElementById("lowStockCount").textContent =
            lowStockData.total_alerts;

        // Update inventory table
        renderInventory(products);

        // Update recent orders
        renderRecentOrders(orders);

        console.log("Dashboard loaded successfully!");

    } catch (error) {
        console.error("Dashboard error:", error);
    }
}


// ==========================================
// RENDER INVENTORY
// ==========================================

function renderInventory(products) {
    const table = document.getElementById("inventoryTable");

    table.replaceChildren();

    if (!products.length) {
        const row = table.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 5;
        cell.textContent = "No products available.";
        return;
    }

    products.forEach(product => {
        const row = table.insertRow();

        const status =
            Number(product.quantity) === 0
                ? "Out of Stock"
                : Number(product.quantity) <=
                  Number(product.minimum_stock)
                    ? "Low Stock"
                    : "In Stock";

        const values = [
            product.name,
            product.category,
            `${product.quantity} ${product.unit}`,
            `₹${product.price}`,
            status
        ];

        values.forEach(value => {
            const cell = row.insertCell();
            cell.textContent = value;
        });

        row.cells[4].className =
            status === "Out of Stock"
                ? "stock-out"
                : status === "Low Stock"
                    ? "stock-low"
                    : "stock-good";
    });
}


// ==========================================
// RENDER RECENT ORDERS
// ==========================================

function renderRecentOrders(orders) {
    const table = document.getElementById("ordersTable");

    table.replaceChildren();

    if (!orders.length) {
        const row = table.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 4;
        cell.textContent = "No orders recorded yet.";
        return;
    }

    // Show latest five orders
    orders.slice().sort(
        (a, b) => b.id - a.id
    ).slice(0, 5).forEach(order => {

        const row = table.insertRow();

        const date = order.created_at
            ? new Date(order.created_at).toLocaleDateString()
            : "N/A";

        [
            `#${order.id}`,
            order.customer_name,
            `₹${Number(order.total_amount).toFixed(2)}`,
            date
        ].forEach(value => {
            const cell = row.insertCell();
            cell.textContent = value;
        });
    });
}


// ==========================================
// LOAD DASHBOARD ON PAGE START
// ==========================================

document.addEventListener("DOMContentLoaded", () => {
    loadDashboardData();
});


// ==========================================
// SALES ANALYTICS DASHBOARD
// ==========================================

const analyticsPeriod = document.getElementById("analyticsPeriod");

function formatCurrency(value) {
    return `₹ ${Number(value || 0).toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    })}`;
}

function renderTopProducts(products) {
    const table = document.getElementById("topProductsTable");
    table.replaceChildren();

    if (!products || products.length === 0) {
        const row = table.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 3;
        cell.textContent = "No product sales in this period.";
        return;
    }

    products.forEach(product => {
        const row = table.insertRow();
        [
            product.product,
            `${Number(product.quantity_sold).toLocaleString("en-IN")}`,
            formatCurrency(product.total_sales)
        ].forEach(value => {
            const cell = row.insertCell();
            cell.textContent = value;
        });
    });
}

function drawRevenueChart(dailySales) {
    const canvas = document.getElementById("revenueTrendChart");
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(rect.width * ratio);
    canvas.height = Math.round(rect.height * ratio);

    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

    const width = rect.width;
    const height = rect.height;
    const padding = { top: 18, right: 16, bottom: 42, left: 66 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const values = dailySales.map(item => Number(item.revenue || 0));
    const maxValue = Math.max(...values, 1);
    const step = maxValue / 4;

    ctx.clearRect(0, 0, width, height);
    ctx.font = "11px Segoe UI, Arial";
    ctx.textBaseline = "middle";

    // Horizontal grid and Y-axis labels
    for (let i = 0; i <= 4; i++) {
        const y = padding.top + chartHeight - (i / 4) * chartHeight;
        const value = step * i;
        ctx.beginPath();
        ctx.strokeStyle = "#293650";
        ctx.lineWidth = 1;
        ctx.moveTo(padding.left, y);
        ctx.lineTo(width - padding.right, y);
        ctx.stroke();
        ctx.fillStyle = "#8c9bb5";
        ctx.textAlign = "right";
        ctx.fillText(value >= 1000 ? `₹${(value / 1000).toFixed(1)}k` : `₹${Math.round(value)}`, padding.left - 10, y);
    }

    const count = dailySales.length;
    const slotWidth = chartWidth / Math.max(count, 1);
    const barWidth = Math.max(3, Math.min(24, slotWidth * 0.55));

    dailySales.forEach((item, index) => {
        const value = Number(item.revenue || 0);
        const barHeight = (value / (maxValue * 1.12)) * chartHeight;
        const x = padding.left + slotWidth * index + (slotWidth - barWidth) / 2;
        const y = padding.top + chartHeight - barHeight;

        ctx.fillStyle = "#7668f5";
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, Math.max(barHeight, value > 0 ? 3 : 0), 4);
        ctx.fill();

        // Show all labels for short periods and spaced labels for longer periods
        const showLabel = count <= 10 || index === 0 || index === count - 1 || index % 5 === 0;
        if (showLabel) {
            const date = new Date(`${item.date}T00:00:00`);
            const label = date.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
            ctx.fillStyle = "#8c9bb5";
            ctx.textAlign = "center";
            ctx.fillText(label, padding.left + slotWidth * index + slotWidth / 2, height - 17);
        }
    });
}

async function loadSalesAnalytics() {
    const period = analyticsPeriod ? analyticsPeriod.value : "weekly";
    const status = document.getElementById("analyticsStatus");
    status.textContent = "Loading sales analytics...";

    const trendDays = period === "daily" ? 1 : period === "monthly" ? 30 : 7;

    try {
        const [summaryResponse, trendResponse] = await Promise.all([
            fetch(`${API_URL}/analytics/summary?period=${encodeURIComponent(period)}`),
            fetch(`${API_URL}/analytics/revenue-trend?days=${trendDays}`)
        ]);

        if (!summaryResponse.ok || !trendResponse.ok) {
            throw new Error("Unable to load analytics. Check the backend API.");
        }

        const summary = await summaryResponse.json();
        const trend = await trendResponse.json();

        document.getElementById("analyticsRevenue").textContent = formatCurrency(summary.total_revenue);
        document.getElementById("analyticsOrders").textContent = Number(summary.total_orders || 0).toLocaleString("en-IN");
        document.getElementById("analyticsAverage").textContent = formatCurrency(summary.average_order_value);

        renderTopProducts(summary.top_products);
        drawRevenueChart(trend.daily_sales || []);

        const caption = period === "daily"
            ? "Revenue for today"
            : period === "monthly"
                ? "Daily revenue for the last 30 days"
                : "Daily revenue for the last 7 days";
        document.getElementById("revenueTrendCaption").textContent = caption;
        status.textContent = `Showing ${summary.date_from} to ${summary.date_to}`;

    } catch (error) {
        console.error("Sales analytics error:", error);
        status.textContent = error.message;
        document.getElementById("analyticsRevenue").textContent = "Unavailable";
        document.getElementById("analyticsOrders").textContent = "--";
        document.getElementById("analyticsAverage").textContent = "--";
        renderTopProducts([]);
    }
}

if (analyticsPeriod) {
    analyticsPeriod.addEventListener("change", loadSalesAnalytics);
}

window.addEventListener("resize", () => {
    if (analyticsPeriod) loadSalesAnalytics();
});

// Load both the existing shop dashboard and sales analytics on page start.
document.addEventListener("DOMContentLoaded", () => {
    loadSalesAnalytics();
});
