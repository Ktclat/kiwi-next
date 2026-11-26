(() => {
  if (location.pathname !== "/fixture.html") return;
  const result = document.getElementById("kiwi-fixture-result");
  if (result) result.textContent = "PASS: MV3 content script ran";
})();
