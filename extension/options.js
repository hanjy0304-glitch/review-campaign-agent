const $ = (id) => document.getElementById(id);

async function render() {
  const { notionDb, status } = await chrome.storage.local.get(["notionDb", "status"]);
  $("db").value = notionDb || "";
  if (!status) return;
  $("status").textContent = status.ok
    ? `${status.at}\n성공: 진행중 ${status.count}건 확인, 새로 추가 ${status.added}, 갱신 ${status.updated}, 변경 없음 ${status.unchanged}`
    : `${status.at}\n실패: ${status.error}`;
}

$("save").onclick = async () => {
  const data = { notionDb: $("db").value.trim() };
  if ($("token").value.trim()) data.notionToken = $("token").value.trim();
  await chrome.storage.local.set(data);
  $("token").value = "";
  $("status").textContent = "저장했습니다.";
};
$("run").onclick = () => {
  $("status").textContent = "수집 중… (잠시 뒤 이 화면을 다시 열어 결과를 확인하세요)";
  chrome.runtime.sendMessage("collect-now");
};
render();
