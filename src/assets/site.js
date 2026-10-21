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

// 문의 버튼 클릭 측정: click_call(전화), click_kakao(카카오톡).
// 클릭만 기록합니다. 실제 통화·상담·예약 완료를 뜻하지 않습니다. 개인정보는 보내지 않습니다.
// 이동을 막지 않도록 preventDefault를 쓰지 않고, 문서 전체에 리스너 하나만 둬서 한 번 클릭에 한 번만 기록됩니다.
(function () {
  var body = document.body;
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a[href]");
    if (!a) return;
    var href = a.getAttribute("href") || "";
    var name = href.indexOf("tel:") === 0 ? "click_call" : (href.indexOf("pf.kakao.com") !== -1 ? "click_kakao" : "");
    if (!name) return;
    var loc = a.getAttribute("data-loc") || (a.closest(".site-header") ? "상단" : a.closest(".actionbar") ? "고정" : a.closest(".closing, .site-footer") ? "하단" : "본문");
    var params = {
      page_path: location.pathname,
      button_location: loc,
      content_group: body.getAttribute("data-group") || "",
      content_topic: body.getAttribute("data-topic") || "",
      transport_type: "beacon"
    };
    if (typeof window.gtag === "function") {
      window.gtag("event", name, params);
    } else {
      (window.dataLayer = window.dataLayer || []).push(Object.assign({ event: name }, params));
    }
  }, { passive: true });
})();
