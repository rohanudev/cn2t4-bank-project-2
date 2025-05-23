// router.js
import { Login } from "./components/login.js";
import { Signup } from "./components/signup.js";
import { Landing } from "./components/landing.js";
import { AccountDetail } from "./components/accountDetail.js";
import { Deposit } from "./components/deposit.js";
import { Withdraw } from "./components/withdraw.js";
import { Transfer } from "./components/transfer.js";

import { UserInfo } from "./components/userinfo.js";
import { UserInfoEdit } from "./components/userinfoEdit.js";
import { AccountCreate } from "./components/accountCreate.js";
import { AccountEdit } from "./components/accountEdit.js";
import { Menu } from "./components/menu.js";
import { Settings } from "./components/settings.js";
import { VerifyEmail } from "./components/verifyEmail.js"

import { state } from './store.js';

const routes = {
  login: Login,
  signup: Signup,
  verifyEmail: VerifyEmail,
  landing: Landing,
  deposit: Deposit,
  withdraw: Withdraw,
  transfer: Transfer,
  userInfo: UserInfo,
  userInfoEdit: UserInfoEdit,
  accountCreate: AccountCreate,
  accountDetail: AccountDetail,
  accountEdit: AccountEdit,
  menu: Menu,
  settings: Settings,
};

let currentScreen = null;

export function goTo(screenName, props) {
  const app = document.getElementById("app");
  if (currentScreen) {
    app.removeChild(currentScreen.el); // 기존 화면 제거
  }

  const component = routes[screenName]();

  component.init?.(props);
  app.appendChild(component.el);

  currentScreen = component;
}