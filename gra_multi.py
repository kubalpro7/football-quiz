import streamlit as st
import os
import random
import time
import difflib
from PIL import Image

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Football Quiz FINAL V8", layout="centered", page_icon="⚽")

# --- CSS (NAPRAWA WYGLĄDU I UKŁADU) ---
st.markdown("""
    <style>
    /* Kontener główny - dopasowany do laptopów */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 5rem !important;
        max-width: 800px;
    }
    .stApp { background-color: #0e1117; }
    
    /* Ukrycie elementów systemowych */
    #MainMenu, footer, header {visibility: hidden;}

    /* Tablica wyników */
    .score-board {
        display: flex; justify-content: space-between; align-items: center;
        background: #262730; padding: 15px; border-radius: 10px;
        font-size: 20px; font-weight: bold; color: white;
        border: 1px solid #444; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    /* Zdjęcie */
    img {
        max-height: 400px !important;
        object-fit: contain;
        border-radius: 12px;
        margin-bottom: 10px;
    }
    
    /* Karty graczy w Lobby */
    .player-box {
        text-align: center; padding: 10px; border-radius: 8px; width: 100%; font-weight: bold; font-size: 16px;
    }
    .p1-box { background-color: #1b5e20; color: #a5d6a7; border: 1px solid #2e7d32; }
    .p2-box { background-color: #0d47a1; color: #90caf9; border: 1px solid #1565c0; }
    
    /* Alerty */
    .turn-alert { text-align: center; color: #ffca28; font-weight: bold; font-size: 18px; margin: 10px 0; }
    
    /* Wyrównanie przycisków w formularzu */
    div[data-testid="column"] { 
        display: flex; 
        align-items: center; 
        justify-content: center;
    }
    /* Powiększenie przycisków */
    button {
        height: 50px !important; 
        font-size: 16px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- GLOBALNY STAN SERWERA (Singleton) ---
class GlobalGameState:
    def __init__(self):
        self.p1_name = None
        self.p2_name = None
        self.p1_score = 0
        self.p2_score = 0
        self.status = "lobby" 
        
        self.current_team = None
        self.current_image = None
        self.image_pool = []
        self.round_id = 0
        self.input_reset_counter = 0 
        self.current_round_starter = "P1" 
        
        self.p1_locked = False
        self.p2_locked = False
        self.who_starts_next = "P1"
        self.winner_last_round = None
        self.last_correct_answer = ""
        
        self.p1_last_seen = time.time()
        self.p2_last_seen = time.time()
        self.disconnect_reason = ""

@st.cache_resource
def get_server_state():
    return GlobalGameState()

server = get_server_state()

# --- LOKALNY STAN (SESJA PRZEGLĄDARKI) ---
if 'my_role' not in st.session_state:
    st.session_state.my_role = None
# Domyślnie włączamy tryb klawiatury dla wygody (Enter działa)
if 'input_mode' not in st.session_state:
    st.session_state.input_mode = True 

# --- FUNKCJE ---
def update_heartbeat(role):
    if role == "P1": server.p1_last_seen = time.time()
    elif role == "P2": server.p2_last_seen = time.time()

def check_disconnections():
    if server.status not in ["playing", "round_over"]: return
    timeout = 10.0 # Tolerancja 10 sekund
    now = time.time()
    if now - server.p1_last_seen > timeout:
        server.status = "disconnected"
        server.disconnect_reason = f"Gracz {server.p1_name} rozłączył się!"
    elif now - server.p2_last_seen > timeout:
        server.status = "disconnected"
        server.disconnect_reason = f"Gracz {server.p2_name} rozłączył się!"

def get_available_leagues(folder):
    if not os.path.exists(folder): return []
    leagues = []
    for item in os.listdir(folder):
        if os.path.isdir(os.path.join(folder, item)) and not item.startswith("."):
            leagues.append(item.replace("_", " "))
    return sorted(leagues)

def load_images_filtered(folder, selected_leagues):
    server.image_pool = []
    if not os.path.exists(folder): return
    for root, dirs, files in os.walk(folder):
        folder_parts = root.split(os.sep)
        match = False
        for part in folder_parts:
            if part.replace("_", " ") in selected_leagues:
                match = True; break
        if match:
            for file in files:
                if file.lower().endswith(('.jpg', '.png', '.jpeg')):
                    team = os.path.basename(root).replace("_", " ")
                    if team == "." or team == folder: continue
                    full_path = os.path.join(root, file)
                    server.image_pool.append((team, full_path))

def start_new_round():
    if not server.image_pool: return
    team, img = random.choice(server.image_pool)
    server.current_team = team
    server.current_image = img
    server.p1_locked = False
    server.p2_locked = False
    server.status = "playing"
    server.winner_last_round = None
    server.round_id += 1
    server.input_reset_counter = 0 
    server.current_round_starter = server.who_starts_next

# --- LOGIKA ODPOWIEDZI ---
def handle_guess(role, guess_text, all_teams):
    """Sprawdza odpowiedź. Jeśli tryb tekstowy - szuka podobieństwa."""
    if not guess_text: return False
    
    # 1. Dokładne dopasowanie (dla listy)
    if guess_text == server.current_team:
        return True
    
    # 2. Przybliżone dopasowanie (dla wpisywania z klawiatury)
    # cutoff=0.6 oznacza że musi być w 60% podobne
    matches = difflib.get_close_matches(guess_text, all_teams, n=1, cutoff=0.5)
    if matches:
        # Jeśli znaleziono podobną nazwę i jest to poprawna drużyna
        if matches[0] == server.current_team:
            return True
            
    return False

def handle_wrong(role):
    server.input_reset_counter += 1
    if role == "P1":
        server.p1_locked = True
        server.p2_locked = False
    else:
        server.p2_locked = True
        server.p1_locked = False

def handle_surrender(role):
    server.input_reset_counter += 1
    if role == "P1": server.p1_locked = True
    else: server.p2_locked = True

def handle_win(winner):
    server.winner_last_round = winner
    server.last_correct_answer = server.current_team
    if winner == "P1":
        server.p1_score += 1
        server.who_starts_next = "P2"
    elif winner == "P2":
        server.p2_score += 1
        server.who_starts_next = "P1"
    server.status = "round_over"

def reset_game():
    server.p1_name = None
    server.p2_name = None
    server.p1_score = 0
    server.p2_score = 0
    server.status = "lobby"
    server.p1_locked = False
    server.p2_locked = False
    server.who_starts_next = "P1"
    server.p1_last_seen = time.time()
    server.p2_last_seen = time.time()

FOLDER_Z_KOSZULKAMI = "."

# --- INICJALIZACJA ---
if st.session_state.my_role:
    update_heartbeat(st.session_state.my_role)
check_disconnections()

# ==============================================================================
# GŁÓWNA PĘTLA APLIKACJI (IF/ELIF ZAPEWNIA BRAK DUCHÓW)
# ==============================================================================

if server.status == "lobby":
    # --- EKRAN 1: LOBBY ---
    st.markdown("<h2 style='text-align: center;'>🏆 LOBBY</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='player-box p1-box'>GOSPODARZ (P1)</div>", unsafe_allow_html=True)
        if server.p1_name:
            st.success(f"✅ {server.p1_name}")
        else:
            n1 = st.text_input("Nick P1", key="n1")
            if st.button("Zajmij P1"):
                if n1:
                    server.p1_name = n1
                    st.session_state.my_role = "P1"
                    update_heartbeat("P1")
                    st.rerun()
    with col2:
        st.markdown("<div class='player-box p2-box'>GOŚĆ (P2)</div>", unsafe_allow_html=True)
        if server.p2_name:
            st.success(f"✅ {server.p2_name}")
        else:
            n2 = st.text_input("Nick P2", key="n2")
            if st.button("Zajmij P2"):
                if n2:
                    server.p2_name = n2
                    st.session_state.my_role = "P2"
                    update_heartbeat("P2")
                    st.rerun()

    st.divider()

    # Konfiguracja (TYLKO w Lobby i TYLKO dla P1)
    if st.session_state.my_role == "P1":
        st.subheader("⚙️ Ustawienia")
        all_leagues = get_available_leagues(FOLDER_Z_KOSZULKAMI)
        selected_leagues = st.multiselect("Wybierz ligi:", all_leagues, default=all_leagues)
        
        st.write("") # Odstęp
        
        if server.p1_name and server.p2_name:
            if not selected_leagues:
                st.error("⚠️ Wybierz min. 1 ligę!")
            else:
                if st.button("START MECZU 🚀", type="primary", use_container_width=True):
                    load_images_filtered(FOLDER_Z_KOSZULKAMI, selected_leagues)
                    if not server.image_pool:
                        st.error("Brak zdjęć w wybranych folderach!")
                    else:
                        server.p1_last_seen = time.time()
                        server.p2_last_seen = time.time()
                        start_new_round()
                        st.rerun()
        else:
            st.warning("⏳ Czekamy na drugiego gracza...")
            time.sleep(1)
            st.rerun()
            
    elif st.session_state.my_role == "P2":
        st.info("⏳ Oczekiwanie na start gry przez Gospodarza...")
        time.sleep(1)
        st.rerun()
    else:
        # Obserwator w lobby
        time.sleep(1)
        st.rerun()

elif server.status == "playing":
    # --- EKRAN 2: ROZGRYWKA ---
    
    # Wyniki
    st.markdown(f"""
    <div class="score-board">
        <span style="color: #66bb6a">{server.p1_name}: {server.p1_score}</span>
        <span style="font-size: 14px; color: #888">VS</span>
        <span style="color: #42a5f5">{server.p2_name}: {server.p2_score}</span>
    </div>
    """, unsafe_allow_html=True)

    # Info o turach
    if server.p1_locked:
        st.markdown(f"<div class='turn-alert'>❌ {server.p1_name} PUDŁO! Tura: {server.p2_name}</div>", unsafe_allow_html=True)
    elif server.p2_locked:
        st.markdown(f"<div class='turn-alert'>❌ {server.p2_name} PUDŁO! Tura: {server.p1_name}</div>", unsafe_allow_html=True)

    # Zdjęcie
    if server.current_image:
        try: st.image(Image.open(server.current_image), use_container_width=True)
        except: st.error("Błąd ładowania zdjęcia")

    # Pobranie listy drużyn
    all_teams = sorted(list(set([x[0] for x in server.image_pool])))

    # Przełącznik trybu (Lista / Klawiatura)
    c_toggle, c_empty = st.columns([1, 2])
    with c_toggle:
        mode_toggle = st.toggle("⌨️ Tryb klawiatury (Enter)", value=st.session_state.input_mode)
        if mode_toggle != st.session_state.input_mode:
            st.session_state.input_mode = mode_toggle
            st.rerun()

    # FORMULARZ ODPOWIEDZI
    # Unikalny klucz formularza (round_id + reset_counter) czyści pola po akcji
    with st.form(key=f"gf_{server.round_id}_{server.input_reset_counter}"):
        
        user_guess = ""
        
        if st.session_state.input_mode:
            # TRYB TEKSTOWY: Wciśnięcie ENTER tutaj automatycznie wysyła formularz (działa jak przycisk ZGŁASZAM)
            user_guess = st.text_input("Wpisz drużynę i wciśnij ENTER:", placeholder="np. Arsenal")
        else:
            # TRYB LISTY: Wybierz myszką
            user_guess = st.selectbox("Wybierz z listy:", [""] + all_teams)

        st.write("") # Odstęp

        # UKŁAD PRZYCISKÓW [3, 1, 1] - Wszystkie w jednej linii
        c1, c2, c3 = st.columns([3, 1, 1])
        
        with c1:
            submit_guess = st.form_submit_button("ZGŁASZAM 🎯", type="primary", use_container_width=True)
        
        with c2:
            submit_surrender = st.form_submit_button("Poddaję🏳️", use_container_width=True)
            
        with c3:
            # Koniec gry tylko dla P1
            if st.session_state.my_role == "P1":
                submit_end = st.form_submit_button("🏁", type="secondary", use_container_width=True, help="Zakończ Grę")
            else:
                submit_end = False

    # --- OBSŁUGA AKCJI ---
    role = st.session_state.my_role
    
    # 1. Koniec gry
    if submit_end and role == "P1":
        server.status = "finished"
        st.rerun()

    # 2. Zgłoszenie (Kliknięcie lub Enter w polu tekstowym)
    if submit_guess and user_guess:
        is_locked = server.p1_locked if role == "P1" else server.p2_locked
        
        if not is_locked:
            if handle_guess(role, user_guess, all_teams):
                handle_win(role) # Trafienie
                st.rerun()
            else:
                st.toast("ŹLE! Blokada!", icon="❌")
                handle_wrong(role)
                st.rerun()
        else:
             st.toast("Jesteś zablokowany! Czekaj na przeciwnika.", icon="⛔")

    # 3. Poddanie
    if submit_surrender:
        handle_surrender(role)
        st.rerun()

    # 4. Automatyczne sprawdzenie czy obaj zablokowani
    if server.p1_locked and server.p2_locked:
        server.winner_last_round = "NIKT"
        server.last_correct_answer = server.current_team
        # Zmiana rozpoczynającego
        if server.current_round_starter == "P1": server.who_starts_next = "P2"
        else: server.who_starts_next = "P1"
        server.status = "round_over"
        st.rerun()

    time.sleep(1) # Odświeżanie stanu gry
    st.rerun()

elif server.status == "round_over":
    # --- EKRAN 3: KONIEC RUNDY ---
    
    # Możliwość zakończenia gry tutaj też
    if st.session_state.my_role == "P1":
        if st.sidebar.button("🏁 ZAKOŃCZ GRĘ", type="primary"):
            server.status = "finished"
            st.rerun()

    # Banner wyniku
    if server.winner_last_round == "P1":
        bg, txt = "#1b5e20", f"🏆 Punkt dla: {server.p1_name}!"
    elif server.winner_last_round == "P2":
        bg, txt = "#0d47a1", f"🏆 Punkt dla: {server.p2_name}!"
    else:
        bg, txt = "#555", "💀 Nikt nie zgadł"
        
    st.markdown(f"""
    <div style='background-color:{bg}; color:white; padding:15px; border-radius:10px; text-align:center; font-size:24px; font-weight:bold; margin-bottom:10px;'>
        {txt}
    </div>
    """, unsafe_allow_html=True)

    # Poprawna odpowiedź
    st.markdown(f"<h3 style='text-align:center; color:#4CAF50;'>{server.last_correct_answer}</h3>", unsafe_allow_html=True)
    
    if server.current_image: 
        st.image(Image.open(server.current_image), use_container_width=True)

    st.divider()

    # Przycisk Dalej (Tylko dla uprawnionego gracza)
    active_player = server.who_starts_next
    if st.session_state.my_role == active_player:
        st.success("Twoja kolej! Rozpocznij rundę.")
        if st.button("NASTĘPNA RUNDA ➡️", type="primary", use_container_width=True):
            start_new_round()
            st.rerun()
    else:
        st.info(f"Czekaj... {active_player} rozpoczyna rundę.")
        st.empty()
        time.sleep(1)
        st.rerun()

elif server.status == "disconnected":
    # --- EKRAN 4: WALKOWER ---
    st.error(f"🚨 WALKOWER! {server.disconnect_reason}")
    st.markdown(f"""
    <div style='background-color:#262730; padding:20px; border-radius:10px; text-align:center;'>
        <h2>Wynik Końcowy</h2>
        <h1 style='color:#66bb6a'>{server.p1_name}: {server.p1_score}</h1>
        <h1 style='color:#42a5f5'>{server.p2_name}: {server.p2_score}</h1>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("WRÓĆ DO LOBBY 🏠", type="primary"):
        reset_game()
        st.rerun()
    time.sleep(2)
    st.rerun()

elif server.status == "finished":
    # --- EKRAN 5: PODSUMOWANIE ---
    st.markdown("<h1 style='text-align:center; color:#4CAF50;'>🏁 KONIEC MECZU 🏁</h1>", unsafe_allow_html=True)
    
    if server.p1_score > server.p2_score:
        msg = f"🏆 WYGRYWA: {server.p1_name}!"
    elif server.p2_score > server.p1_score:
        msg = f"🏆 WYGRYWA: {server.p2_name}!"
    else:
        msg = "🤝 REMIS!"

    st.markdown(f"<h2 style='text-align:center;'>{msg}</h2>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style='background-color:#262730; padding:20px; border-radius:10px; text-align:center; margin-top:20px;'>
        <h1>{server.p1_score} - {server.p2_score}</h1>
    </div>
    """, unsafe_allow_html=True)

    if st.button("ZAGRAJ JESZCZE RAZ (LOBBY) 🔄", type="primary", use_container_width=True):
        reset_game()
        st.rerun()

# Awaryjny reset
if st.sidebar.button("HARD RESET"):
    reset_game()
    st.rerun()





