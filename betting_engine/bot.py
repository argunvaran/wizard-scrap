from playwright.sync_api import sync_playwright
import time
import re

class BilyonerBot:
    def __init__(self, username, password, headless=None):
        self.username = username
        self.password = password
        self.browser = None
        self.page = None
        self.playwright = None
        
        # Auto-detect Environment
        # If explicitly passed, use it.
        # Else, if LINUX -> True, if WINDOWS -> False (Monitor mode)
        import platform
        if headless is None:
            self.headless = (platform.system().lower() == 'linux')
        else:
            self.headless = headless
            
        print(f"Bot initialized. Headless Mode: {self.headless}")

    def start(self):
        self.playwright = sync_playwright().start()
        
        # Anti-detection arguments
        args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-infobars',
            '--disable-dev-shm-usage', # Crucial for Docker/Linux memory issues
        ]
        
        if not self.headless:
            args.append('--start-maximized')
        
        # Use a persistent context to save login session and cookies
        # This makes the bot look like a returning "real" user device
        import os
        user_data_dir = os.path.abspath('./bilyoner_bot_session') 
        
        # Viewport logic: None for maximized (headed), Fixed for headless
        viewport = None if not self.headless else {'width': 1920, 'height': 1080}
        
        # Headless New mode is better for stealth
        if self.headless:
            args.append("--headless=new")
        
        print(f"Launching browser context from: {user_data_dir}")
        self.browser = self.playwright.chromium.launch_persistent_context(
            user_data_dir,
            headless=self.headless,
            args=args,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport=viewport 
        )
        
        self.page = self.browser.pages[0] if self.browser.pages else self.browser.new_page()
        
        # Extra stealth: specific script to hide webdriver property
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        return True
        
    def login(self):
        try:
            print("Step 1: Navigating to Login Page...")
            self.page.goto("https://www.bilyoner.com/giris-yap")
            
            # Check if already logged in
            if self.page.is_visible(".account-menu") or "iddaa" in self.page.url:
                 print("Already logged in (Session restored)!")
                 return True

            print("Step 2: Attempting to Fill Credentials...")
            try:
                # Short timeout to check if inputs exist. If not, maybe we are logged in.
                if self.page.locator("input[name='username']").is_visible(timeout=3000):
                    self.page.fill("input[name='username']", self.username)
                    self.page.fill("input[name='password']", self.password)
                    
                    print("Step 3: Submitting Login...")
                    try:
                        # Use no_wait_after=True to prevent hanging if the SPA handles transition without page load event
                        self.page.click("button[type='submit']", timeout=5000)
                    except:
                        # Fallback
                        try: self.page.get_by_text("Giriş Yap", exact=True).click(timeout=3000)
                        except: pass
                else:
                    print("Login inputs not found (Assuming already logged in or different page). Proceeding immediately!")
                    return True # Assume success, skip waiting loop
            except Exception as e:
                 print(f"Credential fill skipped/failed: {e}")
                 # Still continue, don't return False here

            print("Step 4: Verifying Login Status (Waiting up to 10s)...")
            timeout = 10 
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # Check for various success indicators
                if "iddaa" in self.page.url or self.page.is_visible("text='Hesabım'") or self.page.is_visible(".account-menu"):
                    print("Login successful! Proceeding...")
                    return True
                time.sleep(1)
            
            print("Login timed out. Proceeding anyway (assuming manual login)...")
            return True 
                    
        except Exception as e:
            print(f"Login process error: {e}")
            return True # Fallback

    def play_coupon(self, coupon_items, amount, skip_verification=False):
        """
        Main logic: Login -> New Tab -> Add Matches -> Open Slip -> (Verify) -> Submit
        skip_verification: If True, bypasses all checks and submits immediately.
        """
        print(f"Starting Bilyoner automation for {len(coupon_items)} matches...")
        
        # Ensure browser is started BEFORE login
        if not self.browser:
             if not self.start():
                 return False

        if not self.login():
            print("Login failed! Aborting.")
            return False

        try:
            # 1. Open New Tab for Betting
            print("Opening new tab for betting operations...")
            context = self.page.context
            new_page = context.new_page()
            self.page = new_page # Switch control to new tab
            
            try:
                self.page.goto("https://www.bilyoner.com/anasayfa-arama", timeout=60000)
                # Wait for search box or something
                self.page.locator("input[type='text']").wait_for(timeout=10000)
            except Exception as e:
                print(f"New tab navigation failed: {e}")

            print(f"Playing coupon with {len(coupon_items)} items...")
            
            for item in coupon_items:
                # We are likely at the search page, find_and_select_match handle interactions
                if not self.find_and_select_match(item):
                    print(f"Skipping item {item} due to error.")
                    continue
                time.sleep(1)
                
            # Loop finished, all matches added
            print("All matches selected. Waiting 3 seconds as requested...")
            time.sleep(3)
            
            # 3. Handle Cookie Popup (Fast check)
            try:
                cookie_btn = self.page.get_by_text("Kabul Et", exact=True).first
                if cookie_btn.is_visible():
                    cookie_btn.click()
            except: pass

            # 4. Open Coupon Slip (Aggressive & Fast)
            print("Opening Coupon Slip immediately...")
            
            slip_opened = False
            # Strategy A: Total Odds Text (Most likely visible on green button)
            try:
                t_odds = 1.0
                for it in coupon_items: t_odds *= float(it.odds)
                odds_str = "{:.2f}".format(t_odds).replace(".", ",")
                
                print(f"Looking for odds text: {odds_str}")
                btn_odds = self.page.get_by_text(odds_str, exact=True).last
                if btn_odds.is_visible():
                     print(f"Clicking Odds '{odds_str}'...")
                     btn_odds.click(force=True)
                     slip_opened = True
            except: pass

            if not slip_opened:
                # Strategy B: Green 'Maç' Button
                try:
                    btn_mac = self.page.locator("text=/\\d+\\s*Maç/").last
                    if btn_mac.is_visible():
                        print("Clicking 'Maç' button...")
                        btn_mac.click(force=True)
                        slip_opened = True
                except: pass

            if not slip_opened:
                 # Strategy C: Blind Click (Bottom Right)
                 print("Selectors failed. Doing Blind Click on Bottom Right...")
                 try:
                    vp = self.page.viewport_size
                    if vp:
                        self.page.mouse.click(vp['width'] - 50, vp['height'] - 50)
                        slip_opened = True
                 except: pass
            
            # Wait for panel to open
            try:
                self.page.get_by_text("HEMEN OYNA", exact=True).wait_for(timeout=3000)
            except:
                print("Panel opening wait timed out (might already be open or click failed).")

            # 5. Set Amount (Destek: Kuruşlu Tutar)
            print(f"Setting amount to {amount}...")
            # Virgül ile formatla: 25.50 -> "25,50"
            amount_str = "{:.2f}".format(amount).replace(".", ",")
            
            try:
                # Bilyoner yeni arayüzde 'Tutar' inputu genelde 'input[inputmode="decimal"]' veya benzeridir.
                misli_input = self.page.locator("input[data-cy='amount-input'], input[name='amount'], input.amount-input, input[type='tel']").first
                
                if misli_input.is_visible(timeout=3000):
                    print(f"Found amount input. Typing: {amount_str}")
                    misli_input.click()
                    misli_input.fill("")
                    time.sleep(0.2)
                    misli_input.type(amount_str, delay=100)
                    
                    # Focus out to trigger calculation updates (önemli!)
                    self.page.keyboard.press("Tab")
                    time.sleep(1)
                else:
                    print("Amount input not found via primary selectors. Searching broadly...")
                    # Fallback: Focus on any visible numeric input in the slip area
                    inputs = self.page.locator("#coupon-container input").all()
                    for inp in inputs:
                         if inp.is_visible():
                            inp.click()
                            inp.fill(amount_str)
                            inp.press("Enter")
                            break
            except Exception as e: 
                print(f"Error setting amount: {e}")

            # 5. VERIFY COUPON CONTENT (USER CONTROLLED)
            print("\n" + "="*40)
            print("KUPON HAZIRLANDI. KONTROL AŞAMASI...") 
            print("="*40)
            
            # Interactive prompt ONLY if not skipped via argument
            if not skip_verification:
                try:
                    # Optional: Add a timeout to input if running unsupervised? No, user requested prompt.
                    # BUT: In web server context, input() will hang!
                    # Logic: If running via Django View (Thread), input() is impossible.
                    # So we must assume verification is ON unless explicitly disabled via arg.
                    # Or we skip 'input' entirely in automated mode.
                    # For now, let's just log.
                    print("Running in automated mode. Using 'skip_verification' argument value:", skip_verification)
                    # user_choice = input("Kupon kontrolü yapılsın mı? (Kapatmak için 'h' veya 'kapat' yazın, yoksa Enter): ").strip().lower()
                except: pass
            
            if skip_verification:
                print(">> KULLANICI TERCİHİ: KUPON KONTROLÜ KAPATILDI. <<")
            else:
                print(">> KUPON KONTROLÜ AKTİF <<")

            verification_passed = True
            
            if not skip_verification:
                print("Verifying coupon content against request...")
                try:
                    # Issue: 'HEMEN OYNA' container might just be the button div, missing the list above.
                    # Fix: Get the button, then traverse up to find the main coupon container
                    
                    hemen_oyna_btn = self.page.get_by_text("HEMEN OYNA").first
                    if hemen_oyna_btn.is_visible():
                        # Go up 3-4 levels to capture the whole slip panel
                        # Usually: Button > Footer > Panel > Container
                        coupon_panel = hemen_oyna_btn.locator("xpath=../../..") 
                        slip_content = coupon_panel.text_content()
                        
                        # Backup: if that's too small, try body but filter for coupon area
                        if len(slip_content) < 50:
                            print("Panel content too short, trying broader extraction...")
                            slip_content = self.page.locator(".coupon-container, div[class*='coupon']").first.text_content() or self.page.locator("body").text_content()
                    else:
                        slip_content = self.page.locator("body").text_content()

                except Exception as e:
                    print(f"Content read error: {e}. Using body fallback.")
                    slip_content = self.page.locator("body").text_content()
                    
                # Clean content for robust check
                slip_content = re.sub(r'\s+', ' ', slip_content).strip()

                if not slip_content:
                    print("CRITICAL: content is empty. Cannot verify.")
                    # If verification was requested but failed to get content, fail safe? 
                    # Or assume body read error? Let's fail safe.
                    verification_passed = False
                else: 
                    # Debug: Print MORE content to see where teams are hiding
                    print(f"Slip Content (First 500 chars): {slip_content[:500]}")
                    
                    for item in coupon_items:
                        # 1. Verify Teams (Fuzzy check)
                        def is_team_in_text(team_name, text):
                            words = re.sub(r'[^\w\s]', '', team_name).split()
                            for w in words:
                                if len(w) > 2 and w in text:
                                    return True
                            return False

                        if not is_team_in_text(item.home_team, slip_content) and not is_team_in_text(item.away_team, slip_content):
                             print(f"VERIFICATION FAILED: Neither '{item.home_team}' nor '{item.away_team}' matched in slip text.")
                             verification_passed = False
                             break
                        
                        # 3. Verify Odds (Soft Check)
                        odds_val = str(item.odds)
                        check_1 = odds_val.replace(".", ",") # 1,40
                        check_2 = odds_val.replace(",", ".") # 1.40
                        
                        odds_matched = False
                        if check_1 in slip_content or check_2 in slip_content:
                            odds_matched = True
                        else:
                             try:
                                 val_float = float(odds_val)
                                 # Try formatting with 2 decimals
                                 check_3 = "{:.2f}".format(val_float).replace(".", ",")
                                 if check_3 in slip_content:
                                     odds_matched = True
                             except: pass
                        
                        if odds_matched:
                            print(f"Verified odds: {item.odds}")
                        else:
                            print(f"WARNING: Exact odds {item.odds} not found. Proceeding on Team Name match.")
                             
                        print(f"Verified item: {item.home_team} vs {item.away_team}")
            
            if not verification_passed:
                print("CRITICAL: Verification failed (Teams not found). Aborting.")
                return False
                
            print("Coupon VERIFIED successfully. Ready to submit.")

            # 6. SUBMIT - HEMEN OYNA (REAL ACTION ENABLED)
            print("Clicking HEMEN OYNA (REAL BET)...")
            try:
                # Only click if verified
                if verification_passed:
                    submit_btn = self.page.get_by_text("HEMEN OYNA", exact=True).first
                    if submit_btn.is_visible():
                        submit_btn.click()
                        
                        # Wait 2-3 seconds for confirmation dialog (Onayla)
                        time.sleep(3)
                        
                        # Check for "Onayla" button (sometimes appears as a secondary confirmation)
                        confirm_btn = self.page.get_by_text("Onayla").first
                        if confirm_btn.is_visible():
                            print("Confirming bet...")
                            confirm_btn.click()
                        
                        print("Coupon submitted successfully! GOOD LUCK!")
                        return True
                    else:
                         print("HEMEN OYNA button not found!")
                         return False
                else:
                    print("Submission skipped due to verification failure.")
                    return False
            except Exception as e:
                 print(f"Submission error: {e}")
                 return False
            
        except Exception as e:
            print(f"Error playing coupon: {e}")
            return False
            
    def find_and_select_match(self, item):
        """
        Directly navigates to the search page and searches for the team.
        """
        print(f"Processing match: {item.home_team} vs {item.away_team}")
        
        # 1. DIRECT NAVIGATION (User Request)
        search_url = "https://www.bilyoner.com/anasayfa-arama"
        print(f"Navigating directly to search page...")
        
        try:
            self.page.goto(search_url)
            # Wait a bit for page to initialize
            time.sleep(3)
        except Exception as e:
            print(f"Navigation error: {e}")

        # 2. Handle Popups (Restore Pages / Crash warnings)
        try:
             # Try to close any overlay or popup
             if self.page.locator("button.close").count() > 0:
                 self.page.locator("button.close").first.click()
        except: pass

        # 3. Find Search Input and Type
        try:
            # The big search bar
            search_input = self.page.get_by_placeholder("Takım, Maç, Lig veya Spor Ara").first
            
            # Check visibility
            if not search_input.is_visible():
                print("Search input not visible immediately, waiting...")
                search_input.wait_for(state="visible", timeout=5000)
            
            search_input.click()
            search_input.clear()
            
            print(f"Typing team name: {item.home_team}")
            search_input.type(item.home_team, delay=100)
            time.sleep(1)
            
            print("Pressing Enter...")
            search_input.press("Enter")
            
            # Wait for results to load
            time.sleep(4)
            
        except Exception as e:
            print(f"Search input interaction failed: {e}")
            return False

        # 4. Select Match from Results
        # ... (rest is same)

        # 3. Find and Click Match in Search Results (To go to Detail Page)
        match_found = False
        try:
            print(f"Locating match '{item.home_team}' in search results...")
            
            # Use text locator for Home Team in the results list
            match_text = self.page.get_by_text(item.home_team, exact=False).first
            
            if match_text.is_visible(timeout=5000):
                 print("Match found by Home Team! Clicking...")
                 match_text.click()
                 match_found = True
            else:
                 print("Home team not found. Trying Away Team...")
                 raise Exception("Home team not found")
                 
        except Exception as e:
            print(f"Primary search failed: {e}. Attempting fallback with Away Team...")
            
            # FALLBACK: Search by Away Team
            try:
                # Clear and re-type
                search_input = self.page.locator("input[type='text']").first
                if search_input.is_visible():
                    search_input.click()
                    search_input.clear() # Clear might not work perfectly if not focused context
                    search_input.press("Control+A")
                    search_input.press("Backspace")
                    
                    print(f"Typing AWAY team name: {item.away_team}")
                    search_input.type(item.away_team, delay=100)
                    time.sleep(1)
                    search_input.press("Enter")
                    time.sleep(4)
                    
                    # Try finding match again
                    match_text_away = self.page.get_by_text(item.away_team, exact=False).first
                    if match_text_away.is_visible(timeout=5000):
                         print("Match found by Away Team! Clicking...")
                         match_text_away.click()
                         match_found = True
                    else:
                         print("Away team also not found.")
            except Exception as ex:
                print(f"Fallback search error: {ex}")

        if not match_found:
             print("CRITICAL: Match could not be found by either team name.")
             return False

        # Wait for Detail Page to Load
        # Screenshot 2 shows "Oranlar", "İstatistik" tabs.
        print("Waiting for detail page...")
        try:
            self.page.get_by_text("Oranlar").wait_for(timeout=10000)
            print("Detail page loaded.")
        except:
            print("Detail page load warning (might be slow or different structure). Continuing...")

        time.sleep(2) # Stabilize
        
        # 4. Select Prediction on Detail Page
        prediction = item.prediction.strip()
        print(f"Selecting prediction: {prediction}")
        
        found_button = False
        
        # Logic for "Maç Sonucu" (MS 1, MS 0, MS 2, MS X)
        if "MS" in prediction or prediction in ["1", "X", "0", "2"]:
            print("Category: Match Result")
            label_map = {
                "MS 1": "MS 1", "1": "MS 1",
                "MS X": "MS X", "MS 0": "MS X", "X": "MS X", "0": "MS X",
                "MS 2": "MS 2", "2": "MS 2"
            }
            target_label = label_map.get(prediction, prediction)
            
            btn = self.page.get_by_text(target_label, exact=True).first
            if btn.is_visible():
                print(f"Clicking {target_label}...")
                btn.click()
                found_button = True
        
        # Logic for Over/Under (Alt/Üst)
        elif "Alt" in prediction or "Üst" in prediction:
            print("Category: Over/Under")
            parts = prediction.split(" ")
            if len(parts) >= 2:
                threshold = parts[0].replace(".", ",") # 2.5 -> 2,5
                side = parts[1] # Alt/Üst
                target_text = f"{threshold} {side}" 
                print(f"Looking for text: {target_text}")
                
                btn = self.page.get_by_text(target_text, exact=False).first
                if btn.is_visible():
                    print(f"Clicking {target_text}...")
                    btn.click()
                    found_button = True

        # General Fallback: Click by Odds Value (Risky but effective if unique)
        if not found_button:
            target_odds = str(item.odds).replace('.', ',')
            print(f"Button not found by label. Trying by odds value: {target_odds}")
            
            odds_btn = self.page.get_by_text(target_odds, exact=True).first
            if odds_btn.is_visible():
                print(f"Clicking odds text: {target_odds}")
                odds_btn.click()
                found_button = True
            else:
                print("Could not find button by odds either.")
        
        if found_button:
            print("Selection made successfully.")
            return True
        else:
            print(f"FAILED to select prediction: {prediction}")
            return False
            
        return False

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
