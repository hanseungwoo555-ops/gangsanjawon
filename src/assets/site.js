// 전후 비교 슬라이더와 작업사례 분류 버튼. 스크립트가 없어도 모든 내용은 그대로 보인다.
document.querySelectorAll(".ba").forEach(function (box) {
  var range = box.querySelector("input[type=range]");
  if (!range) return;
  var set = function () { box.style.setProperty("--pos", range.value + "%"); };
  range.addEventListener("input", set);
  set();
});

document.querySelectorAll("[data-filter-group]").forEach(function (group) {
  var target = document.getElementById(group.getAttribute("data-filter-group"));
  if (!target) return;
  group.addEventListener("click", function (e) {
    var btn = e.target.closest("button[data-filter]");
    if (!btn) return;
    var f = btn.getAttribute("data-filter");
    group.querySelectorAll("button").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b === btn));
    });
    target.querySelectorAll("[data-tag]").forEach(function (el) {
      el.hidden = f !== "all" && el.getAttribute("data-tag") !== f;
    });
  });
});

// 인스타그램 썸네일을 누르면 그 자리에서 영상을 재생한다. 막힌 환경에서는 링크로 새 창이 열린다.
document.querySelectorAll(".video-thumb[data-embed]").forEach(function (a) {
  a.addEventListener("click", function (ev) {
    ev.preventDefault();
    var f = document.createElement("iframe");
    f.src = a.getAttribute("data-embed");
    f.title = "인스타그램 영상";
    f.allow = "autoplay; encrypted-media; picture-in-picture";
    var box = document.createElement("div");
    box.className = "video-thumb is-playing";
    box.appendChild(f);
    a.replaceWith(box);
  }, { once: true });
});
