"use strict";
(async () => {
  const number = decodeURIComponent(location.pathname.split("/").pop());
  const storageKey = "checkout:" + number;
  const fragment = new URLSearchParams(location.hash.slice(1)).get("token");
  if (fragment) {
    sessionStorage.setItem(storageKey, fragment);
    history.replaceState(null, "", location.pathname);
  }
  const token = sessionStorage.getItem(storageKey);
  const message = document.getElementById("message");
  const summary = document.getElementById("summary");
  const channels = document.getElementById("channels");
  let api;
  async function request(path, body) {
    const response = await fetch(api + path, {
      method: body ? "POST" : "GET", credentials: "omit",
      headers: {Authorization: "Bearer " + token, "Content-Type": "application/json"},
      ...(body ? {body: JSON.stringify(body)} : {})
    });
    const result = await response.json();
    if (!response.ok) {
      if (response.status === 401) sessionStorage.removeItem(storageKey);
      throw new Error(result.error?.message || "Permintaan gagal");
    }
    return result.data;
  }
  async function load() {
    channels.replaceChildren();
    message.textContent = "";
    try {
      const payment = await request("/public/payments/" + encodeURIComponent(number));
      summary.textContent = payment.payment_no + " — " + payment.currency + " " + payment.amount + " — " + payment.status;
      const options = await request("/public/payments/" + encodeURIComponent(number) + "/channels");
      for (const channel of options.channels) {
        const button = document.createElement("button");
        button.textContent = "Bayar melalui " + channel.name;
        button.onclick = async () => {
          button.disabled = true;
          try {
            const attempt = await request("/public/payments/" + encodeURIComponent(number) + "/attempts", {channel_code: channel.code});
            if (attempt.status === "PAID") { await load(); return; }
            const url = new URL(attempt.instructions.redirect_url);
            if (url.protocol !== "https:" || !["app.midtrans.com", "app.sandbox.midtrans.com"].includes(url.hostname))
              throw new Error("Instruksi pembayaran belum tersedia");
            location.assign(url.href);
          } catch (error) { message.textContent = error.message; button.disabled = false; }
        };
        channels.append(button);
      }
      if (!options.channels.length) message.textContent = "Tidak ada metode pembayaran tersedia untuk transaksi ini.";
    } catch (error) { message.textContent = error.message; }
  }
  document.getElementById("refresh").onclick = load;
  if (!token) { summary.textContent = "Tautan checkout tidak valid atau tidak lengkap."; return; }
  try {
    const config = await fetch("/checkout-config", {credentials: "omit"}).then(r => r.json());
    api = config.api_prefix;
    await load();
  } catch (_) { message.textContent = "Checkout belum dapat dimuat."; }
})();

