// -------------------------------
// Load cart from localStorage
// -------------------------------
window.cartItems = JSON.parse(localStorage.getItem("cartItems")) || [];
window.cartTotal = parseInt(localStorage.getItem("cartTotal")) || 0;
//

// -------------------------------
// Update cart count in top bar
// -------------------------------
window.updateCartCount = function () {
    const el = document.getElementById("cart-count");
    if (el) el.textContent = cartTotal;
};

// Call once on page load
updateCartCount();

// -------------------------------
// Save cart to localStorage
// -------------------------------
function saveCart() {
    localStorage.setItem("cartItems", JSON.stringify(cartItems));
    localStorage.setItem("cartTotal", cartTotal);

    if (cartItems.length === 0 || cartItems.every(i => i.qty === 0)) {
        localStorage.setItem("paymentDone", "1");
    }
}

// -------------------------------
// Add item
// -------------------------------
window.activateQty = function (btn) {
    const wrapper = btn.parentElement;
    const qtyBox = wrapper.querySelector(".qty-box");
    const qtySpan = qtyBox.querySelector(".qty");
    const leftBtn = qtyBox.querySelector(".left-btn");

    const productName = btn.dataset.product;

    // Always start at 1 when Add to Cart is clicked
    qtySpan.textContent = 1;
    leftBtn.textContent = "🗑️";

    // Show qty box, hide Add button
    btn.style.display = "none";
    qtyBox.style.display = "flex";

    // Update cart data
    let item = cartItems.find(i => i.name === productName);

    if (!item) {
        // First time adding this product
        cartItems.push({ name: productName, qty: 1 });
        cartTotal += 1;
    } else {
        // If item existed before, reset it to 1
        item.qty = 1;
    }

    updateCartCount();
    saveCart();
};
// -------------------------------
// Increase quantity
// -------------------------------
window.increaseQty = function (btn) {
    const productName = btn.dataset.product;
    let item = cartItems.find(i => i.name === productName);

    if (item) {
        item.qty += 1;

        // Update UI
        const box = btn.parentElement;
        const qtySpan = box.querySelector(".qty");
        qtySpan.textContent = item.qty;

        // Change delete to minus when qty >= 2
        const leftBtn = box.querySelector(".left-btn");
        leftBtn.textContent = "-";

        saveCart();
    }
};
// -------------------------------
// Decrease quantity
// -------------------------------
window.decreaseQty = function (btn) {
    const productName = btn.dataset.product;
    let item = cartItems.find(i => i.name === productName);

    if (!item) return;

    const box = btn.parentElement;
    const qtySpan = box.querySelector(".qty");
    const leftBtn = box.querySelector(".left-btn");

    if (item.qty === 1) {
        // Remove item
        cartItems = cartItems.filter(i => i.name !== productName);
        cartTotal -= 1;
        updateCartCount();
        saveCart();

        // Reset UI
        const addBtn = box.parentElement.querySelector(".add-btn");
        box.style.display = "none";
        addBtn.style.display = "inline-block";
        return;
    }

    // Reduce qty
    item.qty -= 1;
    qtySpan.textContent = item.qty;

    // If qty becomes 1 → show delete icon
    if (item.qty === 1) {
        leftBtn.textContent = "🗑️";
    }

    saveCart();
};
// -------------------------------
// Restore UI
// -------------------------------
function restoreUI() {
    cartItems.forEach(item => {
        const productName = item.name;

        // Find the product card button
        const addBtn = document.querySelector(`.add-btn[data-product="${productName}"]`);
        if (!addBtn) return;

        const wrapper = addBtn.parentElement;
        const qtyBox = wrapper.querySelector(".qty-box");
        const qtySpan = qtyBox.querySelector(".qty");
        const leftBtn = qtyBox.querySelector(".left-btn");

        // Hide Add button, show qty box
        addBtn.style.display = "none";
        qtyBox.style.display = "flex";

        // Set quantity
        qtySpan.textContent = item.qty;

        // Set left button icon
        leftBtn.textContent = item.qty > 1 ? "−" : "🗑️";
    });
}
document.addEventListener("DOMContentLoaded", restoreUI);
function renderInvoice() {
    const tbody = document.getElementById("invoice-body");
    tbody.innerHTML = "";

    const items = JSON.parse(localStorage.getItem("cartItems")) || [];
    let grandTotal = 0;

    // ⭐ Sort alphabetically by item name
    items.sort((a, b) => a.name.localeCompare(b.name));

    items.forEach(item => {
        const price = productPrices[item.name];
        const safePrice = price ? price : 0;

        const lineTotal = safePrice * item.qty;
        grandTotal += lineTotal;

        const row = document.createElement("tr");

        row.innerHTML = `
            <td>${item.name}</td>
            <td>${item.qty}</td>
            <td>$${safePrice.toFixed(2)}</td>
            <td>$${lineTotal.toFixed(2)}</td>
        `;

        tbody.appendChild(row);
    });

    document.getElementById("grand-total").textContent =
        "$" + grandTotal.toFixed(2);
}

// ⭐ This stays at the bottom
document.addEventListener("DOMContentLoaded", renderInvoice);
document.addEventListener("DOMContentLoaded", () => {
    const paymentDone = localStorage.getItem("paymentDone");

    if (paymentDone === "true") {
        // Clear cart fully
        localStorage.setItem("cartItems", JSON.stringify([]));

        // Reset cart count visually
        const cartCount = document.getElementById("cart-count");
        if (cartCount) cartCount.textContent = 0;

        // Remove flag so it only runs once
        localStorage.removeItem("paymentDone");
    }

    // Always update cart count on load
    if (typeof updateCartCount === "function") {
        updateCartCount();
    }
});
window.clearCart = function () {
    cartItems = [];
    cartTotal = 0;

    saveCart();
    localStorage.setItem("paymentDone", "0");

    updateCartCount();

    // Reset all product UI
    document.querySelectorAll(".qty-box").forEach(box => {
        box.style.display = "none";
    });

    document.querySelectorAll(".add-btn").forEach(btn => {
        btn.style.display = "inline-block";
    });
};
document.addEventListener("DOMContentLoaded", () => {
    const clearBtn = document.getElementById("clear-cart-btn");
    if (clearBtn) clearBtn.addEventListener("click", clearCart);

    resetPaymentFlagIfCartEmpty();
    updateCartCount();
});
document.addEventListener("DOMContentLoaded", () => {

    const hamburgerBtn = document.getElementById("hamburger-btn");
    const sideMenu = document.getElementById("side-menu");
    const closeBtn = document.getElementById("close-side-menu");

    hamburgerBtn.addEventListener("click", () => {
        sideMenu.style.left = "0";
    });

    closeBtn.addEventListener("click", () => {
        sideMenu.style.left = "-260px";
    });
});
