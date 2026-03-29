function addMessage(text, type) {
  const chat = document.getElementById("chat");

  const empty = chat.querySelector(".empty");
  if (empty) empty.remove();

  const div = document.createElement("div");
  div.className = "msg " + type;
  div.innerHTML = text.replace(/\n/g, "<br>");

  chat.appendChild(div);
  div.scrollIntoView();

  return div;
}

function send() {
  const input = document.getElementById("input");
  const btn = document.getElementById("sendBtn");

  const query = input.value.trim();
  if (!query) return;

  input.value = "";
  input.disabled = true;
  btn.disabled = true;

  addMessage(query, "user");

  const botDiv = addMessage('<span class="typing">Typing...</span>', "bot");

  const url = `http://localhost:8000/api/stream?query=${encodeURIComponent(query)}`;
  const evt = new EventSource(url);

  botDiv.innerText = "";

  evt.onopen = () => {
    botDiv.innerText = "";
  };

  evt.onmessage = (e) => {
    if (e.data === "[DONE]") {
      input.disabled = false;
      btn.disabled = false;
      input.focus();
      evt.close();
      return;
    }

    botDiv.innerText += e.data;
  };

  evt.onerror = () => {
    input.disabled = false;
    btn.disabled = false;
    input.focus();
    evt.close();
  };
}

// Enter key support
document.getElementById("input").addEventListener("keypress", function (e) {
  if (e.key === "Enter") send();
});

// Always focus input on load
window.onload = () => {
  document.getElementById("input").focus();
};
