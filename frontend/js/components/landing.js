import { API_BASE_URL } from "../config.js"; // API 주소
import { goTo } from "../router.js"; // 라우터 이동
import { state } from "../store.js"; // 상태 관리
import { authorizedFetch } from "../utils.js";

export function Landing() {
  let localState = {
    userId: state.userId,
    email: state.userEmail,
    userName: state.userName,
    accounts: [],
  };

  const el = document.createElement("div");
  el.className = "screen";
  el.id = "screen-landing";

  async function init(props) {
    if (!localState.userId) {
      console.error("[ERROR] userId is missing");
      return;
    }

    sessionStorage.removeItem("selected_account_id");

    // fetchUserData();
    renderLanding();
    
    await fetchAccounts();
    renderAccounts();

    bindEvents();
  }

  async function fetchUserData() {
    try {
      const res = await authorizedFetch(`${API_BASE_URL}/api/users/${localState.userId}`);
      if (!res.ok) throw new Error(`HTTP error! Status: ${res.status}`);
      const data = await res.json();
      localState.userName = data.name;
      updateUI();
    } catch (error) {
      console.error("[ERROR] Failed to fetch user data:", error);
    }
  }

  async function fetchAccounts() {
    const MIN_SKELETON_DURATION = 500; // 최소 0.5초 보여주기
    const startTime = Date.now();

    try {
      const res = await authorizedFetch(`${API_BASE_URL}/api/accounts/user/${localState.userId}`);
      if (!res.ok) throw new Error(`HTTP error! Status: ${res.status}`);
      const data = await res.json();

      const elapsed = Date.now() - startTime;
      const delay = Math.max(0, MIN_SKELETON_DURATION - elapsed);

      await new Promise(resolve => setTimeout(resolve, delay)); // 최소 시간 보장
      
      localState.accounts = data;
      
    } catch (error) {
      console.error("[ERROR] Failed to fetch accounts:", error);
    }
  }

  function renderLanding() {
    el.innerHTML = `
      <div class="landing">
        <div class="header-container">
          <div class="user-name" id="user-name">${localState.userName}</div>
          <div class="icons">
            <img src="../../assets/icons/menu-btn.png" class="menu-btn" />
          </div>
        </div>
        <div class="center-wrapper">
          <div class="account-list-container">
            <div class="account-info-card skeleton-item">
              <div class="account-header">
                <div class="account-nick skeleton-box" style="width: 60px; height: 20px;"></div>
                <div class="balance-container">
                  <div class="balance skeleton-box" style="width: 80px; height: 24px;"></div>
                </div>
              </div>
              <div class="transfer-btn skeleton-box" style="width: 63px; height: 29px; border-radius: 20px;"></div>
            </div>
          </div>
          <div class="single-btn-dark-box add-account-btn">
            <div class="single-btn-dark-text">+</div>
          </div>
        </div>
      </div>
    `;
  }


  function renderAccounts() {
    const accountListContainer = el.querySelector(".account-list-container");
    accountListContainer.innerHTML = "";

    localState.accounts.forEach(account => {
      const accountCard = document.createElement("div");
      accountCard.className = `account-info-card ${account.status === "OPEN" ? "open" : "closed"}`;
      accountCard.dataset.accountId = account.account_id;
      accountCard.dataset.accountNumber = account.account_number;
      accountCard.innerHTML = `
        <div class="status-indicator ${account.status === "OPEN" ? "open" : "closed"}"></div>
        <div class="account-header">
          <div class="account-nick">${account.nickname}</div>
          <div class="balance-container">
            <div class="balance">${account.balance.toLocaleString()}</div>
            <div class="money-unit">원</div>
          </div>
        </div>
        ${account.status === "OPEN" ? `
          <div id="btn-go-transfer" class="transfer-btn">
            <div class="transfer-text">이체</div>
          </div>
        ` : ""}
      `;

      // ✅ 카드 클릭 시 account-detail로 이동 (이체 버튼 클릭 제외)
      accountCard.addEventListener("click", (event) => {
        if (!event.target.closest(".transfer-btn")) {
          console.log("[INFO] 계좌상세이동:", account.account_id);
          goTo("accountDetail", { accountId: account.account_id });
        }
      });

      accountListContainer.appendChild(accountCard);
    });

    bindTransferEvents(); // 이체 버튼 바인딩
  }

  function bindEvents() {
    el.querySelector(".add-account-btn").addEventListener("click", () => {
      goTo("accountCreate", {});
    });

    el.querySelector(".menu-btn").addEventListener("click", () => {
      goTo("menu", {});
    });
  }

  function bindTransferEvents() {
    const transferButtons = el.querySelectorAll(".transfer-btn");
    transferButtons.forEach(btn => {
      btn.addEventListener("click", (event) => {
        const accountCard = event.target.closest(".account-info-card");
        const accountNumber = accountCard.dataset.accountNumber;
        goTo("transfer", { accountNumber });
      });
    });
  }

  return { el, init };
}
