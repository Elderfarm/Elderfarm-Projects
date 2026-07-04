// Lykkehjul — rent visuelt engagement. Den faktiske gavekort-vinder findes
// separat ved tilfældig lodtrækning blandt alle tilmeldte (se admin-siden).
(function () {
  const SEGMENTS = [
    "Held og lykke! 🍀", "Super spin! 🎉", "Flot forsøg! 👍", "Du er med! ✨",
    "Go' timing! 🔥", "Fedt spin! 🙌", "Held i vente! 🎯", "Nice! 🌟",
  ];
  const wheel = document.getElementById("wheel");
  const spinBtn = document.getElementById("spin-btn");
  const resultBox = document.getElementById("spin-result");
  const signupSection = document.getElementById("signup-section");
  const spinResultInput = document.getElementById("spin_result_input");

  if (!wheel || !spinBtn) return;

  const n = SEGMENTS.length;
  const segmentAngle = 360 / n;

  const gradientStops = SEGMENTS.map((_, i) => {
    const hue = Math.round((360 / n) * i);
    const from = i * segmentAngle;
    const to = (i + 1) * segmentAngle;
    return `hsl(${hue}, 70%, 55%) ${from}deg ${to}deg`;
  }).join(", ");
  wheel.style.background = `conic-gradient(${gradientStops})`;

  SEGMENTS.forEach((label, i) => {
    const midAngle = i * segmentAngle + segmentAngle / 2;
    const wrap = document.createElement("div");
    wrap.className = "wheel-label-wrap";
    wrap.style.transform = `rotate(${midAngle}deg)`;
    const text = document.createElement("span");
    text.className = "wheel-label-text";
    text.textContent = label;
    wrap.appendChild(text);
    wheel.appendChild(wrap);
  });

  let spun = false;

  spinBtn.addEventListener("click", function () {
    if (spun) return;
    spun = true;
    spinBtn.disabled = true;
    spinBtn.textContent = "Spinner...";

    const winnerIndex = Math.floor(Math.random() * n);
    const extraSpins = 5;
    const targetAngle = 360 * extraSpins + (360 - winnerIndex * segmentAngle) - segmentAngle / 2;

    wheel.style.transition = "transform 4s cubic-bezier(0.17, 0.67, 0.12, 0.99)";
    wheel.style.transform = `rotate(${targetAngle}deg)`;

    setTimeout(function () {
      const resultText = SEGMENTS[winnerIndex];
      resultBox.textContent = resultText;
      resultBox.classList.add("visible");
      if (spinResultInput) spinResultInput.value = resultText;
      signupSection.classList.add("visible");
      spinBtn.textContent = "Spinnet! 🎊";
      signupSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 4100);
  });
})();
