const API_URL = "http://localhost:8000/process";

const filesInput = document.getElementById("files");
const processBtn = document.getElementById("processBtn");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const template = document.getElementById("resultTemplate");

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#f87171" : "#93c5fd";
}

function downloadXml(filename, content) {
  const blob = new Blob([content], { type: "application/xml" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.replace(/\.xml$/i, "") + "-anonymized.xml";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function renderResults(results) {
  resultsEl.innerHTML = "";
  for (const item of results) {
    const node = template.content.cloneNode(true);
    node.querySelector(".filename").textContent = item.filename;
    node.querySelector(".before").textContent = item.original_xml;
    node.querySelector(".after").textContent = item.anonymized_xml;
    node.querySelector(".meta").textContent = JSON.stringify(item.metadata, null, 2);
    node.querySelector(".download").addEventListener("click", () => {
      downloadXml(item.filename, item.anonymized_xml);
    });
    resultsEl.appendChild(node);
  }
}

processBtn.addEventListener("click", async () => {
  const files = filesInput.files;
  if (!files || files.length === 0) {
    setStatus("Please select at least one XML file.", true);
    return;
  }
  if (files.length > 5) {
    setStatus("Maximum 5 XML files are supported per run.", true);
    return;
  }

  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }

  setStatus("Processing files...");
  processBtn.disabled = true;

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      body: form,
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Failed to process files");
    }

    const data = await response.json();
    renderResults(data.results || []);
    setStatus(`Done. Processed ${data.count} file(s).`);
  } catch (error) {
    setStatus(`Error: ${error.message}`, true);
  } finally {
    processBtn.disabled = false;
  }
});
