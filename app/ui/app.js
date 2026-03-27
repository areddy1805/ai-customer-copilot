function addMessage(text, type) {
  const div = document.createElement("div");
  div.className = "msg " + type;
  div.innerHTML = text.replace(/\n/g, "<br>");
  document.getElementById("chat").appendChild(div);
  div.scrollIntoView();
  return div;
}

function send() {
  const input = document.getElementById("input");
  const query = input.value.trim();

  if (!query) return;

  input.value = "";
  input.disabled = true;

  addMessage(query, "user");

  const botDiv = addMessage("...", "bot");
  botDiv.innerHTML = "";

  const url = `http://localhost:8000/api/stream?query=${encodeURIComponent(query)}`;
  const evt = new EventSource(url);

  evt.onmessage = (e) => {
    botDiv.innerHTML += e.data.replace(/\n/g, "<br>");
  };

  evt.onerror = () => {
    input.disabled = false;
    evt.close();
  };
}

document.getElementById("input").addEventListener("keypress", function (e) {
  if (e.key === "Enter") send();
});
