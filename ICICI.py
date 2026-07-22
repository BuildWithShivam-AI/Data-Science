import os
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

# --- Config (move real values into a .env, don't commit them) ---
URL = (
    "https://myaadhaar.uidai.gov.in/verify-email-mobile/en"
)
ACCOUNT_NO = os.getenv("ICICI_ACCOUNT_NO", "058501516873")
MOBILE_NO = os.getenv("ICICI_MOBILE_NO", "8097181878")
ACCOUNT_TYPE = os.getenv("ICICI_ACCOUNT_TYPE", "Bank Account")  # which radio to pick

OUT_DIR = "captures"
os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Frame-aware element finder
# ---------------------------------------------------------------------------
def find_in_any_frame(driver, locators, timeout=20, require_visible=True):
    """Find the first matching element across the main document AND every
    iframe. If require_visible, only returns a displayed element. Leaves the
    driver switched into the frame holding it. Raises TimeoutException if none."""
    end = time.time() + timeout

    def search_current():
        for by, val in locators:
            for el in driver.find_elements(by, val):
                try:
                    if not require_visible or el.is_displayed():
                        return el
                except StaleElementReferenceException:
                    continue
        for idx in range(len(driver.find_elements(By.TAG_NAME, "iframe"))):
            try:
                frame = driver.find_elements(By.TAG_NAME, "iframe")[idx]
                driver.switch_to.frame(frame)
            except (StaleElementReferenceException, IndexError):
                continue
            hit = search_current()
            if hit is not None:
                return hit
            driver.switch_to.parent_frame()
        return None

    while time.time() < end:
        driver.switch_to.default_content()
        hit = search_current()
        if hit is not None:
            return hit
        time.sleep(0.5)
    raise TimeoutException(f"No locator matched (visible={require_visible}): {locators}")


def find_field(driver, locators):
    """Quick visible probe, then fall back to the element even if is_displayed()
    is falsely False (the page's opacity/A-B tricks). set_value works via JS so
    it doesn't need the element to be 'interactable' — no need to wait long."""
    try:
        return find_in_any_frame(driver, locators, timeout=2, require_visible=True)
    except TimeoutException:
        return find_in_any_frame(driver, locators, timeout=8, require_visible=False)


def set_value(driver, el, value, label, extra_events=()):
    """Fast field set: inject the value in ONE JS call and fire the events the
    page's handlers listen for (keydown/input/change/keyup/blur + any extra), so
    validators (isNumber, checkMob, mobLogicalexpEnq) run — without typing char
    by char. Verifies the value stuck."""
    events = ["focus", "keydown", "input", "change", "keyup", "blur"] + list(extra_events)
    got = driver.execute_script(
        """
        const el = arguments[0], val = arguments[1], evts = arguments[2];
        el.scrollIntoView({block:'center'});
        el.focus();
        el.value = val;
        evts.forEach(t => el.dispatchEvent(new Event(t, {bubbles:true})));
        return el.value;
        """,
        el, value, events,
    )
    ok = got == value
    print(f"[fill] {label}: '{got}'  {'OK' if ok else 'CHECK'}")
    return ok


# ---------------------------------------------------------------------------
# Step 1: pick the login-type radio (fields are hidden until you do)
# ---------------------------------------------------------------------------
def select_login_type(driver, wanted):
    """Ensure the wanted account-type radio is selected. IMPORTANT: clicking a
    radio fires callRadioEvent() which RESUBMITS the form and reloads the page.
    So if the wanted radio is already checked (Bank Account is, by default),
    we do NOT click — that avoids a needless reload."""
    radios = driver.find_elements(
        By.CSS_SELECTOR, "input[name='CustomLoginGetUserIDFG.USER_ACCOUNT_FLAG']"
    )
    print(f"[radio] {len(radios)} login-type options found:")
    chosen = chosen_value = None
    already_checked = False
    for r in radios:
        val = r.get_attribute("value")
        title = r.get_attribute("title") or ""   # e.g. "Bank Account"
        checked = r.is_selected()
        print(f"   value={val!r}  title={title!r}  checked={checked}")
        if wanted.lower() in title.lower():
            chosen, chosen_value, already_checked = r, val, checked
    if chosen is None and radios:
        print(f"[radio] '{wanted}' not matched by title; defaulting to first option.")
        chosen = radios[0]
        chosen_value = chosen.get_attribute("value")
        already_checked = chosen.is_selected()
    if chosen is None:
        raise NoSuchElementException("No USER_ACCOUNT_FLAG radios on page.")

    if already_checked:
        print(f"[radio] '{wanted}' ({chosen_value}) already selected — no click needed.")
        return

    print(f"[radio] selecting {chosen_value!r} ({wanted}); page will reload...")
    old_url = driver.current_url
    driver.execute_script("arguments[0].click();", chosen)  # triggers form resubmit
    try:
        WebDriverWait(driver, 15).until(
            lambda d: d.current_url != old_url
            or d.find_elements(By.ID, "CustomLoginGetUserIDFG.ACCOUNT_ID")
        )
    except TimeoutException:
        pass
    time.sleep(1.5)


# ---------------------------------------------------------------------------
# Step 2: fill the real text field directly (ACCOUNT_ID / MOBILE_NUMBER).
# These carry their own validators: account onkeypress=isNumber,
# mobile oninput=checkMob(...). send_keys fires real key events so those run.
# ---------------------------------------------------------------------------
def fill_field(driver, field_id, value, label):
    el = find_field(driver, [(By.ID, field_id)])
    return set_value(driver, el, value, label)


# ---------------------------------------------------------------------------
# Step 3: solve the arithmetic captcha (OPER holds the question, RES the answer)
# ---------------------------------------------------------------------------
def solve_captcha(driver):
    # Gather any text that might contain the "a + b" question
    candidates = []
    for by, val in [
        (By.ID, "CustomLoginGetUserIDFG.VERIFICATION_CODE_OPER"),
        (By.CSS_SELECTOR, "[id*='VERIFICATION_CODE_OPER']"),
        (By.CSS_SELECTOR, "[id*='CAPTCHA'], [class*='captcha'], [class*='verification']"),
    ]:
        for el in driver.find_elements(by, val):
            for txt in (el.get_attribute("value"), el.text,
                        el.get_attribute("alt"), el.get_attribute("title")):
                if txt:
                    candidates.append(txt)

    expr = None
    for txt in candidates:
        m = re.search(r"(\d+)\s*([+\-x×*])\s*(\d+)", txt)
        if m:
            expr = m
            print(f"[captcha] question found: '{txt.strip()}'")
            break

    if not expr:
        print("[captcha] Could not read a math question automatically "
              f"(candidates: {candidates}). Solve it manually in the browser.")
        return False

    a, op, b = int(expr.group(1)), expr.group(2), int(expr.group(3))
    result = a + b if op == "+" else a - b if op == "-" else a * b
    print(f"[captcha] {a} {op} {b} = {result}")

    res_field = find_field(
        driver,
        [
            (By.ID, "CustomLoginGetUserIDFG.VERIFICATION_CODE_RES"),
            (By.CSS_SELECTOR, "input[id*='VERIFICATION_CODE_RES']"),
        ],
    )
    # keydown extra event so onkeyup=mobLogicalexpEnq runs (enables Go + sets
    # the required hidden MNDESCRIPTION_WLOF field).
    return set_value(driver, res_field, str(result), "captcha",
                     extra_events=("keydown",))


# ---------------------------------------------------------------------------
# Capture / diagnostics
# ---------------------------------------------------------------------------
def shot(driver, name):
    driver.switch_to.default_content()
    path = os.path.join(OUT_DIR, f"{name}.png")
    driver.save_screenshot(path)
    print(f"[screenshot] {path}")
    return path


def dump_page(driver, name):
    driver.switch_to.default_content()
    with open(os.path.join(OUT_DIR, f"{name}.html"), "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    body = driver.find_element(By.TAG_NAME, "body").text
    with open(os.path.join(OUT_DIR, f"{name}.txt"), "w", encoding="utf-8") as f:
        f.write(body)
    print(f"[dump] {name}.html + {name}.txt")
    return body


def extract_data(driver):
    driver.switch_to.default_content()
    data = {"tables": [], "fields": {}}
    for t_idx, table in enumerate(driver.find_elements(By.TAG_NAME, "table")):
        rows = []
        for row in table.find_elements(By.TAG_NAME, "tr"):
            cells = row.find_elements(By.XPATH, "./td | ./th")
            values = [c.text.strip() for c in cells]
            if any(values):
                rows.append(values)
        if rows:
            data["tables"].append({"index": t_idx, "rows": rows})
    for el in driver.find_elements(By.XPATH, "//input | //select"):
        el_id = el.get_attribute("id") or el.get_attribute("name")
        val = el.get_attribute("value")
        if el_id and val:
            data["fields"][el_id] = val
    return data


def diagnose(driver):
    driver.switch_to.default_content()
    inputs = driver.find_elements(By.TAG_NAME, "input")
    print(f"\n[diag] iframes: {len(driver.find_elements(By.TAG_NAME, 'iframe'))}, "
          f"inputs: {len(inputs)}")
    for i, inp in enumerate(inputs[:30]):
        try:
            vis = inp.is_displayed()
        except StaleElementReferenceException:
            vis = "?"
        print(f"   input[{i}] id={inp.get_attribute('id')!r} "
              f"type={inp.get_attribute('type')!r} visible={vis}")


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------
def build_driver():
    opts = webdriver.ChromeOptions()
    opts.page_load_strategy = "eager"          # return on DOMContentLoaded, don't wait for every asset
    opts.add_argument("--disable-gpu")
    opts.add_argument("--start-maximized")
    # skip image downloads — the captcha is text math, so nothing visual is needed
    opts.add_experimental_option(
        "prefs", {"profile.managed_default_content_settings.images": 2}
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    return webdriver.Chrome(service=Service(), options=opts)


def main():
    driver = build_driver()
    wait = WebDriverWait(driver, 20)

    try:
        driver.get(URL)
        # wait only until the account field exists (no fixed sleep)
        WebDriverWait(driver, 20).until(
            lambda d: d.find_elements(By.ID, "CustomLoginGetUserIDFG.ACCOUNT_ID")
        )
        shot(driver, "00_landing")

        # 1) pick the account type — reveals the account/mobile fields
        select_login_type(driver, ACCOUNT_TYPE)

        # 2) fill the real account + mobile fields (visible after radio picked)
        fill_field(driver, "CustomLoginGetUserIDFG.ACCOUNT_ID", ACCOUNT_NO, "account")
        fill_field(driver, "CustomLoginGetUserIDFG.MOBILE_NUMBER", MOBILE_NO, "mobile")

        # 3) solve the math captcha
        solved = solve_captcha(driver)

        print("Fields filled." + ("" if solved else " (captcha needs manual entry)"))
        shot(driver, "01_filled_form")

        if not solved:
            input("\n>>> Enter the captcha answer in the browser, then press Enter to submit...")

        # 4) submit (Go)
        submit = find_field(
            driver,
            [(By.ID, "VALIDATE_ACC_MOBILE_EMAIL"),
             (By.NAME, "Action.VALIDATE_ACC_MOBILE_EMAIL")],
        )
        try:
            wait.until(lambda d: submit.is_enabled())
        except TimeoutException:
            print("Go still disabled — forcing enabled (diagnostic).")
            driver.execute_script("arguments[0].removeAttribute('disabled');", submit)
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", submit)
        submit.click()
        print("Submitted.")

        old_url = driver.current_url
        try:
            wait.until(lambda d: d.current_url != old_url
                       or "otp" in d.page_source.lower())
        except TimeoutException:
            print("Page didn't visibly change; capturing anyway.")

        time.sleep(1)
        shot(driver, "02_after_submit")
        dump_page(driver, "02_after_submit")

        input("\n>>> Complete OTP / login in the browser, then press Enter to capture data...")
        shot(driver, "03_after_otp")
        dump_page(driver, "03_after_otp")

        data = extract_data(driver)
        print("\n=== Extracted data ===")
        print(f"Tables found: {len(data['tables'])}")
        for tbl in data["tables"]:
            print(f"\nTable #{tbl['index']}:")
            for row in tbl["rows"]:
                print("  " + " | ".join(row))
        print(f"\nFields: {data['fields']}")

    except Exception as e:
        import traceback
        print(f"[error] {type(e).__name__}: {e}")
        traceback.print_exc()
        shot(driver, "99_error")
        dump_page(driver, "99_error")
        diagnose(driver)
    finally:
        input("Press Enter to close the browser...")
        driver.quit()


if __name__ == "__main__":
    main()
