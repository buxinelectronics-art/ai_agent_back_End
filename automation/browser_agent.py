import time, random
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from ai.question_answerer import answer_application_question

class BrowserAgent:
    def __init__(self, headless=True, human_like=True):
        self._pw      = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=headless,
            args=["--no-sandbox","--disable-blink-features=AutomationControlled"]
        )
        self._ctx  = self._browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            viewport={"width":1440,"height":900}, locale="en-US"
        )
        self._page = self._ctx.new_page()
        self.human = human_like

    def _delay(self, lo=0.5, hi=2.0):
        if self.human: time.sleep(random.uniform(lo, hi))

    def _type(self, el, text):
        for ch in text:
            el.type(ch)
            if self.human: time.sleep(random.uniform(0.04, 0.13))

    def _click(self, sel):
        el = self._page.query_selector(sel)
        if el:
            if self.human:
                b = el.bounding_box()
                if b:
                    self._page.mouse.move(
                        b["x"]+b["width"]/2+random.uniform(-3,3),
                        b["y"]+b["height"]/2+random.uniform(-2,2)
                    )
                    time.sleep(random.uniform(0.1,0.25))
            el.click()

    def _detect_ats(self, url):
        u = url.lower()
        if "greenhouse.io" in u: return "greenhouse"
        if "lever.co" in u:      return "lever"
        if "linkedin.com" in u:  return "linkedin"
        return "generic"

    def _fill_questions(self, user_id, job):
        for el in self._page.query_selector_all("textarea, input[type='text']"):
            try:
                lid   = el.get_attribute("id") or ""
                label = ""
                if lid:
                    lb = self._page.query_selector(f"label[for='{lid}']")
                    if lb: label = lb.inner_text()
                if not label:
                    label = el.get_attribute("placeholder") or ""
                if not label: continue
                ans = answer_application_question(label, user_id, job)
                if ans:
                    el.click(); el.fill("")
                    self._type(el, ans)
                    self._delay(0.2, 0.7)
            except Exception:
                continue

    def apply(self, apply_url, resume_path, cover_path, user_id, job, auto_answer):
        try:
            self._page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
            self._delay(1, 3)
            ats = self._detect_ats(apply_url)
            if ats == "linkedin":
                return self._linkedin(resume_path, user_id, job, auto_answer)
            return self._generic(resume_path, cover_path, user_id, job, auto_answer)
        except PWTimeout:
            return {"success": False, "reason": "timeout"}
        except Exception as ex:
            return {"success": False, "reason": str(ex)}

    def _linkedin(self, resume_path, user_id, job, auto_answer):
        try:
            self._click(".jobs-apply-button")
            self._delay(1.5, 2.5)
        except Exception:
            return {"success": False, "reason": "Easy Apply button not found"}
        for _ in range(12):
            if auto_answer: self._fill_questions(user_id, job)
            self._delay(0.5, 1.5)
            if self._page.query_selector("button[aria-label='Submit application']"):
                self._click("button[aria-label='Submit application']")
                self._delay(2, 3)
                return {"success": True}
            elif self._page.query_selector("button[aria-label='Continue to next step']"):
                self._click("button[aria-label='Continue to next step']")
            else:
                break
        return {"success": False, "reason": "Could not complete LinkedIn flow"}

    def _generic(self, resume_path, cover_path, user_id, job, auto_answer):
        try:
            inputs = self._page.query_selector_all("input[type='file']")
            if inputs: inputs[0].set_input_files(resume_path)
            if len(inputs) > 1: inputs[1].set_input_files(cover_path)
        except Exception:
            pass
        if auto_answer: self._fill_questions(user_id, job)
        self._delay(1, 2)
        for sel in ["input[type='submit']","button[type='submit']","button.submit"]:
            if self._page.query_selector(sel):
                self._click(sel); self._delay(2, 4)
                return {"success": True}
        return {"success": False, "reason": "Submit button not found"}

    def close(self):
        try: self._browser.close(); self._pw.stop()
        except Exception: pass
