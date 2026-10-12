const tokenInput = document.getElementById("paired-token");
if (tokenInput) {
  history.replaceState(null, "", "/logs");
  document.getElementById("copy-token").addEventListener("click", async () => {
    tokenInput.select();
    const status = document.getElementById("copy-status");
    status.textContent = "Copying…";
    let copied = false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await Promise.race([
          navigator.clipboard.writeText(tokenInput.value),
          new Promise((_, reject) =>
            setTimeout(
              () => reject(new Error("Clipboard permission pending")),
              2000,
            ),
          ),
        ]);
        copied = true;
      } else copied = document.execCommand("copy");
    } catch {
      /* Keep the token selected for manual copying. */
    }
    status.textContent = copied
      ? "Token copied."
      : "Press Ctrl+C or use your device’s Copy command.";
  });
}
